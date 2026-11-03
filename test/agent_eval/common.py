#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Helpers shared by the agent evaluation tasks: task discovery, workspace setup, check results,
a simulated SoC session (Verilator simulation + litex_server on its UARTBone bridge) and a board
session (litex_server on the UARTBone bridge of a loaded board)."""

import os
import sys
import time
import json
import shutil
import signal
import socket
import tempfile
import subprocess
import importlib.util

ROOT_DIR  = os.path.dirname(os.path.abspath(__file__))
TASKS_DIR = os.path.join(ROOT_DIR, "tasks")

# Tasks --------------------------------------------------------------------------------------------

def list_tasks():
    """Return the task names (directories of tasks/ with a TASK.md)."""
    return sorted(t for t in os.listdir(TASKS_DIR) if os.path.exists(os.path.join(TASKS_DIR, t, "TASK.md")))

def task_dir(task):
    if task not in list_tasks():
        raise ValueError(f"Unknown task {task} (available: {', '.join(list_tasks())}).")
    return os.path.join(TASKS_DIR, task)

def task_prompt(task):
    with open(os.path.join(task_dir(task), "TASK.md"), encoding="utf-8") as f:
        return f.read()

def task_module(task, name):
    """Import tasks/<task>/<name>.py (check or solution)."""
    filename = os.path.join(task_dir(task), f"{name}.py")
    spec     = importlib.util.spec_from_file_location(f"agent_eval_{task}_{name}", filename)
    module   = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def task_tier(task):
    """Tier of task: v1 (fault visible in the source), v2 (fault only visible at runtime)."""
    return getattr(task_module(task, "check"), "TIER", "v1")

def task_hardware(task):
    """Board needed by task (None for the simulation and offline tasks)."""
    return getattr(task_module(task, "check"), "HARDWARE", None)

def hardware_enabled(board):
    """Hardware tasks only run on a host with the board, enabled with LITEX_AGENT_EVAL_HW=<board>
    (comma-separated list)."""
    return board in os.environ.get("LITEX_AGENT_EVAL_HW", "").split(",")

def setup_task(task, workdir):
    """Create a fresh workspace for task in workdir (copy of tasks/<task>/workspace, plus the
    task's setup hook if any) and return the prompt to give to the agent."""
    if os.path.exists(workdir) and os.listdir(workdir):
        raise ValueError(f"Workspace {workdir} is not empty.")
    shutil.copytree(os.path.join(task_dir(task), "workspace"), workdir, dirs_exist_ok=True)
    shutil.copy(os.path.join(task_dir(task), "TASK.md"), os.path.join(workdir, "TASK.md"))
    check = task_module(task, "check")
    if hasattr(check, "setup"):
        check.setup(workdir)
    return task_prompt(task)

# Check Results ------------------------------------------------------------------------------------

class CheckResult:
    """Outcome of a check: a list of named checks, passed when all of them pass."""
    def __init__(self, task):
        self.task   = task
        self.checks = []
        self.error  = None

    def add(self, name, passed, detail=""):
        self.checks.append({"name": name, "passed": bool(passed), "detail": str(detail)})
        return bool(passed)

    @property
    def passed(self):
        return self.error is None and len(self.checks) > 0 and all(c["passed"] for c in self.checks)

    def to_dict(self):
        return {"task": self.task, "passed": self.passed, "checks": self.checks, "error": self.error}

    def to_json(self):
        return json.dumps(self.to_dict(), indent=2)

# Simulated SoC Session ----------------------------------------------------------------------------

class SimError(Exception):
    pass

def tcp_listening(port, host="localhost"):
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False

def _log_tail(filename, lines=30):
    try:
        with open(filename, encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except OSError:
        return ""

class SimSession:
    """Build and run a simulation target (a target.py taking --uart-tcp-port and --output-dir),
    start a litex_server on its UARTBone bridge and open a RemoteClient on it.

    Processes are started in their own session and stopped by process group (PID), the build
    directory is temporary.
    """
    def __init__(self, target, uart_port, server_port, args=None, timeout=900):
        self.target      = os.path.abspath(target)
        self.uart_port   = uart_port
        self.server_port = server_port
        self.args        = [] if args is None else list(args)
        self.timeout     = timeout
        self.sim         = None
        self.server      = None
        self.bus         = None
        self.build_dir   = None

    def _start(self, cmd, log, cwd=None):
        return subprocess.Popen(cmd, cwd=cwd, stdout=open(log, "w"), stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=True)

    def _wait_port(self, port, proc, log, timeout):
        start = time.time()
        while not tcp_listening(port):
            if proc.poll() is not None:
                raise SimError(f"{os.path.basename(log)} exited ({proc.returncode}):\n{_log_tail(log)}")
            if (time.time() - start) > timeout:
                raise SimError(f"Nothing listens on port {port} after {timeout}s:\n{_log_tail(log)}")
            time.sleep(0.5)

    def start(self):
        from litex.tools.litex_client import RemoteClient
        for port in [self.uart_port, self.server_port]:
            if tcp_listening(port):
                raise SimError(f"TCP port {port} is already in use.")
        self.build_dir = tempfile.mkdtemp(prefix="litex_agent_eval_")
        self.csr_csv   = os.path.join(self.build_dir, "csr.csv")
        self.sim_log   = os.path.join(self.build_dir, "sim.log")
        self.sim = self._start([sys.executable, self.target,
            f"--uart-tcp-port={self.uart_port}",
            f"--output-dir={self.build_dir}"] + self.args,
            log = self.sim_log,
            cwd = os.path.dirname(self.target))
        self._wait_port(self.uart_port, self.sim, self.sim_log, self.timeout)
        server_log  = os.path.join(self.build_dir, "server.log")
        self.server = self._start([sys.executable, "-m", "litex.tools.litex_server",
            "--uart", f"--uart-port=socket://localhost:{self.uart_port}",
            f"--bind-port={self.server_port}"],
            log = server_log)
        self._wait_port(self.server_port, self.server, server_log, 30)
        self.bus = RemoteClient(port=self.server_port, csr_csv=self.csr_csv, timeout=5.0)
        self.bus.open()
        return self

    def stop(self):
        if self.bus is not None:
            self.bus.close()
        for proc in [self.server, self.sim]:
            if proc is None or proc.poll() is not None:
                continue
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
        if self.build_dir is not None:
            shutil.rmtree(self.build_dir, ignore_errors=True)

    def __enter__(self):
        try:
            return self.start()
        except Exception:
            self.stop()
            raise

    def __exit__(self, *args):
        self.stop()

    def console_read(self, timeout=1.0):
        """Read what the SoC printed on its crossover UART (as litex_mcp's console_read)."""
        from litex.tools.litex_mcp import LiteXMCPTools
        tools = LiteXMCPTools(port=self.server_port, csr_csv=self.csr_csv)
        try:
            return tools.console_read(timeout=timeout)["output"]
        finally:
            tools.close()

class BoardSession(SimSession):
    """Start a litex_server on the UARTBone bridge of a loaded board (serial port uart) and open a
    RemoteClient on it (csr_csv: CSR file of the loaded build)."""
    def __init__(self, uart, server_port, csr_csv, baudrate=115200):
        SimSession.__init__(self, target=csr_csv, uart_port=None, server_port=server_port)
        self.uart     = uart
        self.baudrate = baudrate
        self.csr_csv  = csr_csv

    def start(self):
        from litex.tools.litex_client import RemoteClient
        if tcp_listening(self.server_port):
            raise SimError(f"TCP port {self.server_port} is already in use.")
        self.build_dir = tempfile.mkdtemp(prefix="litex_agent_eval_")
        server_log  = os.path.join(self.build_dir, "server.log")
        self.server = self._start([sys.executable, "-m", "litex.tools.litex_server",
            "--uart", f"--uart-port={self.uart}", f"--uart-baudrate={self.baudrate}",
            f"--bind-port={self.server_port}"],
            log = server_log)
        self._wait_port(self.server_port, self.server, server_log, 30)
        self.bus = RemoteClient(port=self.server_port, csr_csv=self.csr_csv, timeout=5.0)
        self.bus.open()
        return self

def run_sim_check(result, target, uart_port, server_port, body, args=None):
    """Run body(session) on a simulation of target, recording build/run errors in result."""
    if not os.path.exists(target):
        result.error = f"{os.path.basename(target)} not found."
        return result
    try:
        with SimSession(target, uart_port, server_port, args=args) as session:
            body(session)
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
    return result
