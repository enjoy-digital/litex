#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""LiteX MCP server: expose a running LiteX SoC to AI agents through the Model Context Protocol.

The server connects to a litex_server (any bridge: UART, JTAG, Ethernet, PCIe, USB, simulation)
and exposes typed tools to identify the SoC, list the CSRs/memory regions/constants of its csr.csv
and read registers and memories. Writes are only exposed with --allow-write.

The tools are implemented in LiteXMCPTools (no MCP dependency, usable/testable from Python); the
MCP SDK (pip install mcp, Python >= 3.10) is only imported when the server is run.
"""

import os
import re
import socket
import sys
import json
import time
import signal
import argparse
import tempfile
import importlib.util
import subprocess

from litex.build.report        import parse_build_reports
from litex.tools.litex_client import RemoteClient

# Helpers ------------------------------------------------------------------------------------------

MAX_READ_WORDS = 4096
MAX_SEQUENCE_OPS  = 20000 # Bus operations of a register sequence (all sweep rows).
MAX_SEQUENCE_ROWS = 4096
MAX_WAIT_TIME  = 600 # Seconds, per litex_job_wait call.

def _strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)

def _tcp_listening(port):
    """Return True/False if a local TCP port is in LISTEN state, None when it cannot be known."""
    found = None
    for f in ["/proc/net/tcp", "/proc/net/tcp6"]:
        try:
            with open(f, encoding="utf-8") as fd:
                lines = fd.readlines()[1:]
        except OSError:
            continue
        found = found or False
        for line in lines:
            local, state = line.split()[1], line.split()[3]
            if state == "0A" and int(local.split(":")[1], 16) == port: # 0A: LISTEN.
                return True
    return found

LITEX_CORES = [
    "litedram", "liteeth", "litepcie", "litesata", "litesdcard", "litespi", "litei2c", "liteiclink",
    "litejesd204b", "litescope", "litehyperbus", "litevideo",
]

def _hex(value):
    return f"0x{value:08x}"

class LiteXMCPError(Exception):
    pass

def _match(filter, name):
    """Name filter: a regex searched in name (a plain substring also works), None matches all."""
    if filter is None or filter == "":
        return True
    try:
        return re.search(filter, name) is not None
    except re.error:
        return filter in name

# Link errors: litex_server not answering, connection dropped (SoC reset, cable, server restart).
LINK_ERRORS = (TimeoutError, ConnectionError, socket.timeout)

def _link(method):
    """Turn a link error into a LiteXMCPError and drop the connection: the next call reconnects."""
    import functools
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except LiteXMCPError:
            raise
        except LINK_ERRORS as e:
            self.close()
            raise LiteXMCPError(f"Link to the SoC through litex_server {self.host}:{self.port} failed "
                f"({type(e).__name__}: {e}). The connection was dropped and the next call reconnects; "
                "if the SoC was reset or reloaded, run litex_check.")
    return wrapper

# LiteX MCP Tools ----------------------------------------------------------------------------------

class LiteXMCPTools:
    """Transport independent implementation of the LiteX MCP tools.

    Every method returns plain Python types (dict/list/str/int) that serialize directly to JSON.
    """
    def __init__(self, host="localhost", port=1234, csr_csv="csr.csv", timeout=2.0, allow_write=False,
        client_cls=RemoteClient, jobs_dir=None):
        self.host        = host
        self.port        = int(port)
        self.csr_csv     = csr_csv
        self.timeout     = float(timeout)
        self.allow_write = allow_write
        self.client_cls  = client_cls
        self.bus         = None
        self.jobs_dir    = jobs_dir
        self.jobs        = {}

    # Connection -----------------------------------------------------------------------------------

    def _get_bus(self):
        if self.bus is None:
            if self.csr_csv is not None and not os.path.exists(self.csr_csv):
                raise LiteXMCPError(f"CSR file {self.csr_csv} not found (use --csr-csv).")
            self.bus = self.client_cls(
                host             = self.host,
                port             = self.port,
                csr_csv          = self.csr_csv,
                timeout          = self.timeout,
                raise_on_timeout = True,
            )
        try:
            self.bus.open()
        except OSError as e:
            self.bus = None
            raise LiteXMCPError(f"Unable to connect to litex_server on {self.host}:{self.port} ({e}).")
        return self.bus

    def close(self):
        if self.bus is not None:
            try:
                self.bus.close()
            except LINK_ERRORS:
                pass
            self.bus = None

    def close_all(self):
        self.close()
        for job_id in list(self.jobs):
            self.job_stop(job_id)

    def _check_write(self):
        if not self.allow_write:
            raise LiteXMCPError("Writes are disabled, restart the server with --allow-write.")

    def _get_csr(self, kind):
        bus = self._get_bus()
        if not hasattr(bus, kind):
            raise LiteXMCPError("No CSR file loaded (use --csr-csv).")
        return getattr(bus, kind)

    def _get_register(self, name):
        bus = self._get_bus()
        if not hasattr(bus, "regs") or not hasattr(bus.regs, name):
            raise LiteXMCPError(f"Register {name} not found in {self.csr_csv}.")
        return getattr(bus.regs, name)

    # Identification -------------------------------------------------------------------------------

    @_link
    def ident(self):
        """Return the SoC identifier string."""
        bus = self._get_bus()
        if not hasattr(bus, "bases") or not hasattr(bus.bases, "identifier_mem"):
            raise LiteXMCPError("SoC has no identifier (identifier_mem not found in the CSR file).")
        ident = ""
        for i in range(256):
            c = chr(bus.read(bus.bases.identifier_mem + 4*i) & 0xff)
            if c == "\0":
                break
            ident += c
        return ident

    @_link
    def check(self):
        """Check the host link: connect, read the identifier and measure the read round-trip."""
        bus   = self._get_bus()
        ident = self.ident()
        reg   = None
        if hasattr(bus, "regs") and hasattr(bus.regs, "ctrl_scratch"):
            reg = bus.regs.ctrl_scratch
        start = time.perf_counter()
        n     = 8
        for _ in range(n):
            if reg is not None:
                reg.read()
            else:
                bus.read(bus.bases.identifier_mem)
        latency = (time.perf_counter() - start)/n
        r = {
            "host"            : self.host,
            "port"            : self.port,
            "ident"           : ident,
            "read_latency_ms" : round(latency*1e3, 3),
            "allow_write"     : self.allow_write,
        }
        if reg is not None:
            r["ctrl_scratch"] = _hex(reg.read())
        return r

    # CSR file -------------------------------------------------------------------------------------

    def list_registers(self, filter=None):
        """List the CSRs (name, address, size in CSR words, mode); filter is a name regex/substring."""
        regs = []
        for name, reg in self._get_csr("regs").__dict__.items():
            if _match(filter, name):
                regs.append({
                    "name"    : name,
                    "address" : _hex(reg.addr),
                    "size"    : reg.length,
                    "mode"    : reg.mode,
                })
        return regs

    def list_memory_regions(self):
        """List the memory regions of the SoC (name, base, size, type)."""
        mems = []
        for name, mem in self._get_csr("mems").__dict__.items():
            mems.append({
                "name" : name,
                "base" : _hex(mem.base),
                "size" : _hex(mem.size),
                "type" : mem.type,
            })
        return mems

    def list_constants(self, filter=None):
        """List the SoC constants (config_*, *_interrupt...); filter is a name regex/substring."""
        constants = self._get_csr("constants")
        return {k: v for k, v in constants.d.items() if _match(filter, k)}

    # Reads ----------------------------------------------------------------------------------------

    @_link
    def read_register(self, name):
        """Read a CSR by name."""
        reg   = self._get_register(name)
        value = reg.read()
        return {"name": name, "address": _hex(reg.addr), "value": value, "value_hex": f"0x{value:x}"}

    def read_registers(self, filter):
        """Read every CSR whose name matches filter (regex/substring)."""
        return [self.read_register(r["name"]) for r in self.list_registers(filter) if r["mode"] in ["rw", "ro"]]

    @_link
    def read_memory(self, address, length=1):
        """Read length 32-bit words at address (incrementing burst)."""
        length = int(length)
        if not (0 < length <= MAX_READ_WORDS):
            raise LiteXMCPError(f"length must be between 1 and {MAX_READ_WORDS} words.")
        bus   = self._get_bus()
        datas = bus.read(int(address), length, burst="incr")
        return {"address": _hex(int(address)), "words": [_hex(d) for d in datas]}

    # Writes (--allow-write) -----------------------------------------------------------------------

    @_link
    def write_register(self, name, value):
        """Write a CSR by name (requires --allow-write)."""
        self._check_write()
        reg = self._get_register(name)
        reg.write(int(value))
        return {"name": name, "address": _hex(reg.addr), "value": int(value)}

    @_link
    def write_memory(self, address, words):
        """Write 32-bit words at address (incrementing burst, requires --allow-write)."""
        self._check_write()
        words = [int(w) for w in words]
        if not (0 < len(words) <= MAX_READ_WORDS):
            raise LiteXMCPError(f"between 1 and {MAX_READ_WORDS} words can be written.")
        bus = self._get_bus()
        bus.write(int(address), words, burst="incr")
        return {"address": _hex(int(address)), "length": len(words)}

    # Register Sequences ---------------------------------------------------------------------------

    def _sequence_target(self, target):
        """A sequence target: a CSR name, or a bus address (int or "0x..." string)."""
        if isinstance(target, bool):
            raise LiteXMCPError(f"Invalid sequence target {target!r}.")
        if isinstance(target, int):
            return None, target
        if isinstance(target, str):
            try:
                return None, int(target, 0)
            except ValueError:
                return self._get_register(target), None
        raise LiteXMCPError(f"Invalid sequence target {target!r} (CSR name or address).")

    @staticmethod
    def _sequence_value(value, binding):
        """A step value: an int, or "$var" taken from the sweep row."""
        if isinstance(value, str) and value.startswith("$"):
            if value[1:] not in binding:
                raise LiteXMCPError(f"Sequence variable {value} not in the sweep row {binding}.")
            value = binding[value[1:]]
        if isinstance(value, bool) or not isinstance(value, int):
            try:
                value = int(value, 0) if isinstance(value, str) else int(value)
            except (TypeError, ValueError):
                raise LiteXMCPError(f"Invalid sequence value {value!r}.")
        return value

    @_link
    def register_sequence(self, steps, sweep=None):
        """Run a list of register steps on the SoC in one call, optionally once per sweep row.

        Steps (dicts), targets are CSR names or bus addresses:
        - {"write": target, "value": int or "$var"}        (requires --allow-write)
        - {"read": target, "as": label, "length": words}  (length: addresses only, default 1)
        - {"poll": target, "mask": int, "equals": int or "$var", "timeout_ms": 100, "as": label}
        - {"wait_us": int}
        sweep: list of variable bindings (ex: [{"gain": 16384, "din": 1000}, ...]); the steps run
        once per row. Returns one row per binding with the reads ({label: value}) and polls
        ({label: {"ok", "value", "tries"}}).
        """
        if not isinstance(steps, list) or not steps or not all(isinstance(st, dict) for st in steps):
            raise LiteXMCPError("steps must be a non-empty list of step dicts.")
        rows = [{}] if not sweep else sweep
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise LiteXMCPError("sweep must be a list of variable bindings (dicts).")
        if len(rows) > MAX_SEQUENCE_ROWS:
            raise LiteXMCPError(f"At most {MAX_SEQUENCE_ROWS} sweep rows.")
        kinds = []
        for st in steps:
            kind = [k for k in ["write", "read", "poll", "wait_us"] if k in st]
            if len(kind) != 1:
                raise LiteXMCPError(f"Step {st} must have exactly one of write/read/poll/wait_us.")
            kinds.append(kind[0])
        if "write" in kinds:
            self._check_write()
        if len(rows)*sum(k != "wait_us" for k in kinds) > MAX_SEQUENCE_OPS:
            raise LiteXMCPError(f"At most {MAX_SEQUENCE_OPS} bus operations per sequence.")

        bus     = self._get_bus()
        start   = time.time()
        results = []
        ops     = 0
        for binding in rows:
            reads, polls = {}, {}
            for kind, st in zip(kinds, steps):
                if kind == "wait_us":
                    time.sleep(max(0, min(float(st["wait_us"]), 1e6))/1e6)
                    continue
                reg, addr = self._sequence_target(st[kind])
                label     = str(st.get("as", st[kind]))
                if kind == "write":
                    value = self._sequence_value(st.get("value"), binding)
                    reg.write(value) if reg is not None else bus.write(addr, value)
                    ops += 1
                elif kind == "read":
                    length = int(st.get("length", 1))
                    if reg is not None:
                        value = reg.read()
                    elif length == 1:
                        value = bus.read(addr)
                    elif 0 < length <= MAX_READ_WORDS:
                        value = bus.read(addr, length, burst="incr")
                    else:
                        raise LiteXMCPError(f"length must be between 1 and {MAX_READ_WORDS} words.")
                    reads[label] = value
                    ops += 1
                else:
                    mask     = self._sequence_value(st.get("mask", 0xffffffff), binding)
                    equals   = self._sequence_value(st.get("equals", 1), binding)
                    deadline = time.time() + max(0, min(float(st.get("timeout_ms", 100)), 10000))/1e3
                    tries    = 0
                    while True:
                        value = reg.read() if reg is not None else bus.read(addr)
                        tries += 1
                        ops   += 1
                        if (value & mask) == equals or time.time() > deadline:
                            break
                    polls[label] = {"ok": (value & mask) == equals, "value": value, "tries": tries}
            row = {"vars": binding, "reads": reads} if sweep else {"reads": reads}
            if polls:
                row["polls"] = polls
            results.append(row)
        return {"rows": results, "operations": ops, "elapsed_ms": round((time.time() - start)*1e3, 1)}

    # Connection selection -------------------------------------------------------------------------

    def connect(self, host=None, port=None, csr_csv=None, timeout=None):
        """Select the litex_server/CSR file to use (ex: another board or a simulation) and check it."""
        self.close()
        self.host    = self.host    if host    is None else host
        self.port    = self.port    if port    is None else int(port)
        self.csr_csv = self.csr_csv if csr_csv is None else csr_csv
        self.timeout = self.timeout if timeout is None else float(timeout)
        return self.check()

    # Introspection (no board needed) --------------------------------------------------------------

    @staticmethod
    def _boards_dir():
        try:
            import litex_boards.targets
        except ImportError:
            raise LiteXMCPError("LiteX-Boards is not installed.")
        return os.path.dirname(litex_boards.targets.__file__)

    def list_boards(self, filter=None):
        """List the LiteX-Boards targets (name, vendor); filter is a name regex/substring."""
        boards = []
        for f in sorted(os.listdir(self._boards_dir())):
            name = f[:-3]
            if not f.endswith(".py") or name.startswith("_"):
                continue
            if _match(filter, name):
                boards.append({"name": name, "vendor": name.split("_")[0]})
        return boards

    def board_info(self, name, sections=("Target",)):
        """Describe a LiteX-Boards target: FPGA device, toolchain family and its command-line options.

        sections selects the option groups of the target's --help (ex: Target, SoC, Builder, Vivado
        toolchain); an empty list returns them all.
        """
        targets_dir = self._boards_dir()
        target_file = os.path.join(targets_dir, f"{name}.py")
        if not re.fullmatch(r"[a-z0-9_]+", name) or not os.path.exists(target_file):
            raise LiteXMCPError(f"Board {name} not found (see litex_list_boards).")
        info = {"name": name, "target": target_file}

        # Platform: FPGA device and vendor platform class.
        platform_file = os.path.join(os.path.dirname(targets_dir), "platforms", f"{name}.py")
        if os.path.exists(platform_file):
            with open(platform_file, encoding="utf-8") as f:
                platform = f.read()
            info["platform"] = platform_file
            m = re.search(r"class Platform\((\w+)\)", platform)
            if m:
                info["platform_class"] = m.group(1)
            m = re.search(r"Platform\.__init__\(\s*self\s*,\s*[\"']([^\"']+)[\"']", platform)
            if m:
                info["device"] = m.group(1)
            # Devices selected by variant: device = {"variant": "device", ...}[variant].
            m = re.search(r"device\s*=\s*\{(.*?)\}", platform, re.S)
            if m:
                devices = dict(re.findall(r"[\"']([^\"']+)[\"']\s*:\s*[\"']([^\"']+)[\"']", m.group(1)))
                if devices:
                    info["devices"] = devices

        # Options: from the target's --help, split by group.
        r = subprocess.run([sys.executable, "-m", f"litex_boards.targets.{name}", "--help"],
            capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            raise LiteXMCPError(f"{name} --help failed: {r.stderr.strip()[-500:]}")
        groups  = {}
        current = None
        for line in r.stdout.splitlines():
            m = re.fullmatch(r"(\S.*) options:", line)
            if m:
                current = m.group(1)
                groups[current] = []
            elif current is not None:
                groups[current].append(line)
        info["option_groups"] = list(groups.keys())
        info["options"]       = {k: "\n".join(v).strip() for k, v in groups.items()
            if not sections or k in sections}
        return info

    def list_cpus(self, filter=None):
        """List the CPUs supported by LiteX (name, family, data width, variants)."""
        from litex.soc.cores.cpu import CPUS
        cpus = []
        for name, cpu in sorted((k, v) for k, v in CPUS.items() if k):
            if _match(filter, name):
                cpus.append({
                    "name"       : name,
                    "human_name" : getattr(cpu, "human_name", name),
                    "family"     : getattr(cpu, "family", None),
                    "data_width" : getattr(cpu, "data_width", None),
                    "variants"   : sorted(getattr(cpu, "variants", None) or []),
                })
        return cpus

    def list_cores(self):
        """List the LiteX ecosystem cores and whether they are installed."""
        cores = []
        for name in LITEX_CORES:
            spec = importlib.util.find_spec(name)
            cores.append({
                "name"      : name,
                "installed" : spec is not None,
                "path"      : None if spec is None else os.path.dirname(spec.origin or ""),
            })
        return cores

    # Jobs (simulations, servers, builds) ----------------------------------------------------------

    def _get_jobs_dir(self):
        if self.jobs_dir is None:
            self.jobs_dir = tempfile.mkdtemp(prefix="litex_mcp_")
        os.makedirs(self.jobs_dir, exist_ok=True)
        return self.jobs_dir

    def _start_job(self, kind, cmd, cwd=None, info=None):
        if not isinstance(cmd, list) or not all(isinstance(c, str) for c in cmd):
            raise LiteXMCPError("Command arguments must be a list of strings.")
        job_id = f"{kind}{len(self.jobs)}"
        log    = os.path.join(self._get_jobs_dir(), f"{job_id}.log")
        with open(log, "wb") as f:
            # Own process group: stopping the job stops all its children (toolchains, Verilator...).
            proc = subprocess.Popen(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, start_new_session=True,
                env=dict(os.environ, PYTHONUNBUFFERED="1"))
        self.jobs[job_id] = {"proc": proc, "cmd": cmd, "cwd": cwd, "log": log, "start": time.time(),
            "info": info or {}}
        return self.job_status(job_id, tail=0)

    def _get_job(self, job_id):
        if job_id not in self.jobs:
            raise LiteXMCPError(f"Job {job_id} not found (see litex_list_jobs).")
        return self.jobs[job_id]

    @staticmethod
    def _read_log(log):
        with open(log, "r", encoding="utf-8", errors="replace") as f:
            return _strip_ansi(f.read())

    def job_status(self, job_id, tail=40):
        """Status of a job: running, return code, elapsed time, log file and its last lines."""
        job        = self._get_job(job_id)
        returncode = job["proc"].poll()
        status = {
            "job"        : job_id,
            "command"    : " ".join(job["cmd"]),
            "running"    : returncode is None,
            "returncode" : returncode,
            "elapsed_s"  : round(time.time() - job["start"], 1),
            "log"        : job["log"],
        }
        status.update(job["info"])
        if tail:
            status["log_tail"] = self._read_log(job["log"]).splitlines()[-int(tail):]
        return status

    def job_wait(self, job_id, pattern=None, timeout=60):
        """Wait until the job's log matches pattern (regex), the job ends or timeout (s) expires."""
        job     = self._get_job(job_id)
        timeout = min(float(timeout), MAX_WAIT_TIME)
        regex   = None if not pattern else re.compile(pattern, re.MULTILINE)
        start   = time.time()
        match   = None
        while True:
            ended = job["proc"].poll() is not None
            if regex is not None:
                m = regex.search(self._read_log(job["log"]))
                if m:
                    match = m.group(0)
                    break
            if ended or (time.time() - start) > timeout:
                break
            time.sleep(0.2)
        status = self.job_status(job_id)
        status["matched"]  = match
        status["timeout"]  = (match is None) and status["running"]
        return status

    def job_stop(self, job_id):
        """Stop a job and all its child processes."""
        job  = self._get_job(job_id)
        proc = job["proc"]
        if proc.poll() is None:
            for sig in [signal.SIGTERM, signal.SIGKILL]:
                try:
                    os.killpg(proc.pid, sig)
                except ProcessLookupError:
                    break
                try:
                    proc.wait(timeout=5)
                    break
                except subprocess.TimeoutExpired:
                    pass
        return self.job_status(job_id, tail=10)

    def list_jobs(self):
        """List the jobs started by this server."""
        return [self.job_status(job_id, tail=0) for job_id in self.jobs]

    # Simulation -----------------------------------------------------------------------------------

    def sim_start(self, args=None, output_dir=None):
        """Start litex_sim (Verilator) with args; the console output goes to the job log."""
        args       = [] if args is None else list(args)
        output_dir = os.path.abspath(output_dir or os.path.join(self._get_jobs_dir(), f"sim{len(self.jobs)}"))
        os.makedirs(output_dir, exist_ok=True)
        cmd = [sys.executable, "-m", "litex.tools.litex_sim", "--non-interactive",
            f"--output-dir={output_dir}"] + args
        # Run from the output directory: files written to the current directory (analyzer.csv of
        # --with-analyzer) stay with the build.
        if "--with-analyzer" in args:
            # LiteScope writes analyzer.csv when the run exits: generate it first with a quick
            # elaboration (no compilation, no run) so captures are possible during the simulation.
            r = subprocess.run(cmd + ["--no-compile"], cwd=output_dir, capture_output=True, text=True,
                timeout=300)
            if r.returncode != 0:
                raise LiteXMCPError(f"litex_sim elaboration failed: {(r.stdout + r.stderr)[-1000:]}")
        return self._start_job("sim", cmd, cwd=output_dir, info={
            "output_dir"   : output_dir,
            "csr_csv"      : os.path.join(output_dir, "csr.csv"),
            "analyzer_csv" : os.path.join(output_dir, "analyzer.csv"),
        })

    # Console (crossover UART) ---------------------------------------------------------------------

    def _xover(self, name="uart_xover"):
        bus  = self._get_bus()
        regs = getattr(bus, "regs", None)
        if regs is None or not hasattr(regs, f"{name}_rxtx") or not hasattr(regs, f"{name}_rxempty"):
            raise LiteXMCPError(f"No {name} crossover UART in the SoC (build with --uart-name=crossover or crossover+uartbone).")
        self._xover_rxfull = getattr(regs, f"{name}_rxfull", None)
        return getattr(regs, f"{name}_rxtx"), getattr(regs, f"{name}_rxempty")

    def _console_drain(self, rxtx, rxempty, max_bytes):
        data   = bytearray()
        rxfull = getattr(self, "_xover_rxfull", None)
        while len(data) < max_bytes:
            if rxfull is not None and rxfull.read():
                # Full FIFO: read 16 characters in one burst (as litex_term's crossover).
                data += bytes(v & 0xff for v in self._get_bus().read(rxtx.addr, 16, burst="fixed"))
            elif not rxempty.read():
                data.append(rxtx.read() & 0xff)
            else:
                break
        return data

    @_link
    def console_read(self, timeout=1.0, max_bytes=4096):
        """Read what the SoC printed on its console (crossover UART), until it stays idle for timeout s."""
        rxtx, rxempty = self._xover()
        data  = bytearray()
        start = time.time()
        while (time.time() - start) < min(float(timeout), MAX_WAIT_TIME) and len(data) < int(max_bytes):
            chunk = self._console_drain(rxtx, rxempty, int(max_bytes) - len(data))
            if chunk:
                data += chunk
                start = time.time()
            else:
                time.sleep(0.05)
        return {"output": _strip_ansi(data.decode("utf-8", errors="replace"))}

    @_link
    def console_command(self, command, expect="litex>", timeout=10.0, max_bytes=16384):
        """Send a command line to the SoC console (ex: a BIOS command) and read until expect (regex).

        A command that resets the SoC (ex: reboot) also resets the UART bridge: the link error is
        absorbed, the connection re-opened and the boot output read until expect.
        """
        self._check_write()
        rxtx, rxempty = self._xover()
        self._console_drain(rxtx, rxempty, max_bytes) # Discard pending output.
        for c in command + "\n":
            rxtx.write(ord(c))
        data       = bytearray()
        regex      = re.compile(expect) if expect else None
        start      = time.time()
        reconnects = 0
        while (time.time() - start) < min(float(timeout), MAX_WAIT_TIME) and len(data) < int(max_bytes):
            try:
                chunk = self._console_drain(rxtx, rxempty, int(max_bytes) - len(data))
            except LINK_ERRORS:
                # SoC/bridge reset after the command: re-open the connection and continue reading.
                self.close()
                reconnects += 1
                time.sleep(0.5)
                try:
                    rxtx, rxempty = self._xover()
                except (LiteXMCPError,) + LINK_ERRORS:
                    self.close()
                continue
            data += chunk
            text  = _strip_ansi(data.decode("utf-8", errors="replace"))
            # Match after the echoed command line.
            if regex is not None and regex.search(text.split("\n", 1)[-1] if "\n" in text else ""):
                return {"output": text, "matched": True, "reconnects": reconnects}
            if not chunk:
                time.sleep(0.05)
        return {"output": _strip_ansi(data.decode("utf-8", errors="replace")), "matched": False,
            "reconnects": reconnects}

    # LiteScope ------------------------------------------------------------------------------------

    @staticmethod
    def _scope_driver_class():
        try:
            from litescope.software.driver.analyzer import LiteScopeAnalyzerDriver
        except ImportError:
            raise LiteXMCPError("LiteScope is not installed.")
        return LiteScopeAnalyzerDriver

    @staticmethod
    def _scope_layouts(analyzer_csv):
        if not os.path.exists(analyzer_csv):
            raise LiteXMCPError(f"Analyzer file {analyzer_csv} not found (written by the build next to csr.csv).")
        config, layouts = {}, {}
        with open(analyzer_csv, encoding="utf-8") as f:
            for line in f:
                item = line.strip().split(",")
                if len(item) < 4:
                    continue
                if item[0] == "config":
                    config[item[2]] = int(item[3])
                elif item[0] == "signal":
                    layouts.setdefault(int(item[1]), []).append((item[2], int(item[3])))
        return config, layouts

    def scope_list(self, analyzer_csv="analyzer.csv"):
        """List the LiteScope analyzer groups and signals (with widths), depth and sample rate."""
        config, layouts = self._scope_layouts(analyzer_csv)
        return {
            "depth"      : config.get("depth"),
            "samplerate" : config.get("samplerate"),
            "groups"     : {g: [{"name": n, "width": w} for n, w in l] for g, l in layouts.items()},
        }

    @_link
    def scope_capture(self, analyzer_csv="analyzer.csv", group=0, triggers=None, offset=32, length=None,
        subsampling=1, timeout=10, signals=None, max_changes=32, name="analyzer"):
        """Arm the LiteScope analyzer, wait for the trigger and return the capture as data.

        triggers: list of {"signal": name, "type": "rising"|"falling"|"value", "value": "0x10"} (no
        trigger: immediate capture). The result gives, per signal, the value at the trigger, the
        number of transitions and the first changes (sample index, value); the full capture is
        also saved as a VCD file.
        """
        _, layouts = self._scope_layouts(analyzer_csv)
        if int(group) not in layouts:
            raise LiteXMCPError(f"Group {group} not found in {analyzer_csv}.")
        bus = self._get_bus()
        if not hasattr(bus, "regs") or not hasattr(bus.regs, f"{name}_mux_value"):
            raise LiteXMCPError(f"No {name} analyzer in the SoC CSRs.")
        driver = self._scope_driver_class()(bus.regs, name, config_csv=analyzer_csv)
        driver.configure_group(int(group))
        driver.configure_subsampler(int(subsampling))
        layout = dict(layouts[int(group)])
        cond   = {}
        for t in triggers or []:
            if t.get("signal") not in layout:
                raise LiteXMCPError(f"Signal {t.get('signal')} not in group {group}.")
            kind = t.get("type", "rising")
            if kind == "rising":
                driver.add_rising_edge_trigger(t["signal"])
            elif kind == "falling":
                driver.add_falling_edge_trigger(t["signal"])
            elif kind == "value":
                cond[t["signal"]] = str(t["value"])
            else:
                raise LiteXMCPError(f"Unknown trigger type {kind} (rising, falling or value).")
        if cond:
            driver.add_trigger(cond=cond)
        driver.run(offset=int(offset), length=None if length is None else int(length))
        start = time.time()
        while not driver.done():
            if (time.time() - start) > min(float(timeout), MAX_WAIT_TIME):
                return {"triggered": False, "message": "Trigger did not fire before timeout."}
            time.sleep(0.05)
        data = driver.upload()
        vcd  = os.path.join(self._get_jobs_dir(), f"scope{int(time.time()*1e3)}.vcd")
        driver.save(vcd)

        # Per-signal summary.
        # trigger_sample is the nominal trigger position (the pre-trigger offset; the analyzer
        # pipeline can shift the matching sample by a cycle).
        result = {"triggered": True, "samples": len(data), "trigger_sample": driver.offset, "vcd": vcd,
            "signals": {}}
        low = 0
        for sig, width in layouts[int(group)]:
            values = [(d >> low) & (2**width - 1) for d in data]
            low   += width
            if signals and sig not in signals:
                continue
            changes = [(i, v) for i, v in enumerate(values) if i == 0 or v != values[i - 1]]
            result["signals"][sig] = {
                "width"      : width,
                "at_trigger" : hex(values[driver.offset]) if driver.offset < len(values) else None,
                "transitions": len(changes) - 1,
                "changes"    : [[i, hex(v)] for i, v in changes[:int(max_changes)]],
            }
        return result

    # Builds ---------------------------------------------------------------------------------------

    @staticmethod
    def _abspath_args(args):
        # Make the existing relative paths of args (ex: --csr-json=soc.json, --sdram-init=app.bin)
        # absolute: builds run from their output directory.
        r = []
        for a in args:
            opt, sep, value = a.partition("=") if a.startswith("-") else ("", "", a)
            if value and not os.path.isabs(value) and os.path.exists(value):
                value = os.path.abspath(value)
            r.append(opt + sep + value)
        return r

    def build_start(self, target, args=None, output_dir=None, build=True):
        """Start a target build (--build) in the background; target is a LiteX-Boards board name or
        a target script (.py). With build=False, a target script is run as is with args only (ex: a
        simulation target without --build option). --load/--flash (hardware side effects) require
        --allow-write.

        The build runs from output_dir: files written to the current directory (analyzer.csv of a
        LiteScope analyzer) stay with the build; existing relative paths in args are made absolute."""
        args = [] if args is None else self._abspath_args(args)
        if any(a.split("=")[0] in ["--load", "--flash"] for a in args) and not self.allow_write:
            raise LiteXMCPError("--load/--flash act on the hardware, restart the server with --allow-write.")
        if target.endswith(".py"):
            if not os.path.exists(target):
                raise LiteXMCPError(f"Target script {target} not found.")
            cmd = [sys.executable, os.path.abspath(target)]
        elif not build:
            raise LiteXMCPError("build=False runs a target script (.py) only.")
        else:
            self.board_info(target, sections=[]) # Validates the board name.
            cmd = [sys.executable, "-m", f"litex_boards.targets.{target}"]
        if not build:
            output_dir = os.path.abspath(output_dir) if output_dir else None
            cmd += ([f"--output-dir={output_dir}"] if output_dir else []) + args
            info = {"output_dir": output_dir, "csr_csv": os.path.join(output_dir, "csr.csv")} if output_dir else {}
            return self._start_job("run", cmd, info=info, cwd=os.path.dirname(os.path.abspath(target)))
        output_dir = os.path.abspath(output_dir or os.path.join(self._get_jobs_dir(), f"build{len(self.jobs)}"))
        os.makedirs(output_dir, exist_ok=True)
        cmd += ["--build", f"--output-dir={output_dir}"] + [a for a in args if a != "--build"]
        return self._start_job("build", cmd, cwd=output_dir, info={
            "output_dir"   : output_dir,
            "csr_csv"      : os.path.join(output_dir, "csr.csv"),
            "analyzer_csv" : os.path.join(output_dir, "analyzer.csv"),
        })

    def _get_output_dir(self, job=None, output_dir=None):
        if job:
            output_dir = self._get_job(job)["info"].get("output_dir")
        if not output_dir or not os.path.isdir(output_dir):
            raise LiteXMCPError("Build output directory not found (give a build job or an output_dir).")
        return output_dir

    @staticmethod
    def _read_build_info(output_dir):
        filename = os.path.join(output_dir, "build_info.json")
        if not os.path.exists(filename):
            return None
        try:
            with open(filename, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError) as e:
            raise LiteXMCPError(f"Unable to read {filename} ({e}).")

    def build_info(self, job=None, output_dir=None):
        """build_info.json of a build (job or output_dir, default: the directory of the CSR file):
        command, platform/device/toolchain, CPU, sys_clk_freq, generated files and build status."""
        if not job and not output_dir and self.csr_csv is not None:
            output_dir = os.path.dirname(os.path.abspath(self.csr_csv))
        output_dir = self._get_output_dir(job, output_dir)
        info       = self._read_build_info(output_dir)
        if info is None:
            raise LiteXMCPError(f"No build_info.json in {output_dir} (written by the LiteX Builder).")
        return info

    def soc_file(self, name):
        """Contents of a file describing the current SoC (csr.csv, csr.json, build_info.json), found
        with the selected CSR file (see litex_connect)."""
        if self.csr_csv is None:
            raise LiteXMCPError("No CSR file selected (use --csr-csv or litex_connect).")
        csr_csv    = os.path.abspath(self.csr_csv)
        output_dir = os.path.dirname(csr_csv)
        filename   = {
            "csr.csv"         : csr_csv,
            "csr.json"        : os.path.join(output_dir, "csr.json"),
            "build_info.json" : os.path.join(output_dir, "build_info.json"),
        }.get(name)
        if filename is None:
            raise LiteXMCPError(f"Unknown SoC file {name} (csr.csv, csr.json or build_info.json).")
        # A build_info.json gives the actual csr.json location (--soc-json).
        if name == "csr.json":
            info = self._read_build_info(output_dir) or {}
            filename = (info.get("files") or {}).get("csr_json") or filename
        if not os.path.exists(filename):
            raise LiteXMCPError(f"{filename} not found.")
        with open(filename, encoding="utf-8") as f:
            return f.read()

    def build_report(self, job=None, output_dir=None, max_paths=10):
        """Timing (WNS/TNS, per clock, failing paths), utilization and errors of a build."""
        output_dir = self._get_output_dir(job, output_dir)
        r = parse_build_reports(output_dir, max_paths=int(max_paths))
        build_info   = self._read_build_info(output_dir)
        analyzer_csv = ((build_info or {}).get("files") or {}).get("analyzer_csv")
        if analyzer_csv is None and os.path.exists(os.path.join(output_dir, "analyzer.csv")):
            analyzer_csv = os.path.join(output_dir, "analyzer.csv")
        if analyzer_csv is not None:
            r["analyzer_csv"] = analyzer_csv
        if build_info is not None:
            r["build_info"] = build_info
        if job:
            status = self.job_status(job, tail=0)
            r["running"]    = status["running"]
            r["returncode"] = status["returncode"]
        return r

    def server_start(self, args, timeout=300):
        """Start a litex_server with args (ex: --uart --uart-port=socket://localhost:2345 --bind-port=1240).

        Refuses a bind port already in use (another server would silently answer the clients) and,
        for a socket:// UART (simulation), waits until the simulation listens before starting.
        """
        args = list(args)
        line = " ".join(args)
        m    = re.search(r"--bind-port[= ](\d+)", line)
        bind_port = int(m.group(1)) if m else 1234
        if _tcp_listening(bind_port):
            raise LiteXMCPError(f"TCP port {bind_port} is already in use (another litex_server?), "
                "use another --bind-port.")
        m = re.search(r"socket://[^:/\s]+:(\d+)", line)
        if m:
            uart_port = int(m.group(1))
            start     = time.time()
            while _tcp_listening(uart_port) is False:
                if (time.time() - start) > min(float(timeout), MAX_WAIT_TIME):
                    raise LiteXMCPError(f"Nothing listens on TCP port {uart_port} (simulation not ready?).")
                time.sleep(0.5)
        cmd = [sys.executable, "-m", "litex.tools.litex_server"] + args
        r   = self._start_job("server", cmd, info={"bind_port": bind_port})
        # Wait until the server listens (or exits) so the next tool call can connect.
        start = time.time()
        while _tcp_listening(bind_port) is False and self.jobs[r["job"]]["proc"].poll() is None:
            if (time.time() - start) > 10:
                break
            time.sleep(0.1)
        r = self.job_status(r["job"], tail=10)
        r["ready"] = bool(_tcp_listening(bind_port)) and r["running"]
        return r

# MCP Server ---------------------------------------------------------------------------------------

INSTRUCTIONS = """\
Tools to explore LiteX (boards, CPUs, cores) and to observe (and optionally control) a running LiteX
SoC through litex_server.
Start with litex_check to verify the link and the SoC identity before any other access: another
litex_server on the same port would silently be another board. Registers are addressed by their
csr.csv names (list them with litex_list_registers). Memory accesses are 32-bit words on the SoC
main bus. Writes are only available when the server runs with --allow-write.
"""

def _get_server_class():
    try:
        from mcp.server.mcpserver import MCPServer # MCP SDK >= 2.
        return MCPServer
    except ImportError:
        pass
    try:
        from mcp.server.fastmcp import FastMCP     # MCP SDK 1.x.
        return FastMCP
    except ImportError:
        pass
    raise LiteXMCPError("litex_mcp needs the MCP Python SDK (Python >= 3.10): pip3 install mcp")

def _get_resource_error_class():
    try:
        from mcp.server.mcpserver.exceptions import ResourceError # MCP SDK >= 2.
        return ResourceError
    except ImportError:
        pass
    try:
        from mcp.server.fastmcp.exceptions import ResourceError   # MCP SDK 1.x.
        return ResourceError
    except ImportError:
        return LiteXMCPError

def _tool_annotations(read_only, destructive=False):
    # MCP tool hints: clients can run read-only tools freely and ask for approval on the others.
    try:
        from mcp.types import ToolAnnotations
    except ImportError:
        return None
    return ToolAnnotations.model_validate({"readOnlyHint": read_only, "destructiveHint": destructive})

def _get_tool_error_class():
    # Tool errors are only shown to the client as ToolError: MCP SDK >= 2 hides the message of any
    # other exception ("Error executing tool ...").
    try:
        from mcp.server.mcpserver.exceptions import ToolError # MCP SDK >= 2.
        return ToolError
    except ImportError:
        pass
    try:
        from mcp.server.fastmcp.exceptions import ToolError   # MCP SDK 1.x.
        return ToolError
    except ImportError:
        return None

def build_server(tools, server_cls=None):
    import functools
    server_cls  = _get_server_class() if server_cls is None else server_cls
    server      = server_cls("litex", instructions=INSTRUCTIONS)
    tool_error  = _get_tool_error_class()

    def tool(annotations=None):
        # Register fn as a tool, LiteXMCPError raised as the SDK's ToolError (message to the client).
        def register(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                try:
                    return fn(*args, **kwargs)
                except LiteXMCPError as e:
                    if tool_error is None:
                        raise
                    raise tool_error(str(e)) from e
            return server.tool(annotations=annotations)(wrapper)
        return register
    read_only   = _tool_annotations(read_only=True)
    side_effect = _tool_annotations(read_only=False, destructive=False)
    destructive = _tool_annotations(read_only=False, destructive=True)

    # Connection.
    @tool(annotations=read_only)
    def litex_check() -> dict:
        """Check the link to the SoC: identifier, CSR read round-trip latency, write permission."""
        return tools.check()

    @tool(annotations=side_effect)
    def litex_connect(host: str = "", port: int = 0, csr_csv: str = "", timeout: float = 0) -> dict:
        """Select another litex_server (host/port) and/or CSR file (ex: a simulation), then check it.
        timeout (s) is the bus access timeout, to raise on slow links (ex: 10 for a simulation)."""
        return tools.connect(host or None, port or None, csr_csv or None, timeout or None)

    # SoC (read).
    @tool(annotations=read_only)
    def litex_ident() -> str:
        """Return the identifier string of the SoC."""
        return tools.ident()

    @tool(annotations=read_only)
    def litex_list_registers(filter: str = "") -> list:
        """List the SoC CSRs (name, address, size in CSR words, mode), optionally filtered by a name substring."""
        return tools.list_registers(filter or None)

    @tool(annotations=read_only)
    def litex_list_memory_regions() -> list:
        """List the SoC memory regions (name, base, size, type)."""
        return tools.list_memory_regions()

    @tool(annotations=read_only)
    def litex_list_constants(filter: str = "") -> dict:
        """List the SoC constants (configuration, interrupts...), optionally filtered by a name substring."""
        return tools.list_constants(filter or None)

    @tool(annotations=read_only)
    def litex_read_register(name: str) -> dict:
        """Read a CSR by its csr.csv name (ex: ctrl_scratch)."""
        return tools.read_register(name)

    @tool(annotations=read_only)
    def litex_read_registers(filter: str) -> list:
        """Read every readable CSR whose name contains filter (ex: "uart_")."""
        return tools.read_registers(filter)

    @tool(annotations=read_only)
    def litex_read_memory(address: int, length: int = 1) -> dict:
        """Read length 32-bit words from the SoC main bus at address."""
        return tools.read_memory(address, length)

    @tool(annotations=destructive if tools.allow_write else read_only)
    def litex_register_sequence(steps: list[dict], sweep: list[dict] = []) -> dict:
        """Run register steps on the SoC in one call (one model turn instead of one per register),
        optionally once per sweep row. Use it for configure-then-read sequences, polls and sweeps.

        steps (targets: CSR names from litex_list_registers, or bus addresses):
          {"write": "scaler_gain", "value": 16384}  or  {"write": 805306392, "value": "$limit"}
          {"read": "scaler_dout", "as": "dout"}      ({"length": n} for n words at an address)
          {"poll": "scaler_status", "mask": 1, "equals": 1, "timeout_ms": 100}
          {"wait_us": 10}
        sweep: variable bindings, the steps run once per row, "$name" in a value takes the row's
        value. Ex: [{"din": 0}, {"din": 1000}, {"din": 65535}] with {"write": ..., "value": "$din"}.
        Returns {"rows": [{"vars", "reads": {label: value}, "polls": {...}}], "operations", "elapsed_ms"}.
        Writes require --allow-write.
        """
        return tools.register_sequence(steps, sweep or None)

    # SoC (write, only exposed with --allow-write).
    if tools.allow_write:
        @tool(annotations=destructive)
        def litex_write_register(name: str, value: int) -> dict:
            """Write a CSR by its csr.csv name."""
            return tools.write_register(name, value)

        @tool(annotations=destructive)
        def litex_write_memory(address: int, words: list[int]) -> dict:
            """Write 32-bit words to the SoC main bus at address."""
            return tools.write_memory(address, words)

    # Introspection (no board needed).
    @tool(annotations=read_only)
    def litex_list_boards(filter: str = "") -> list:
        """List the LiteX-Boards targets (name, vendor), optionally filtered by a name substring (ex: "arty")."""
        return tools.list_boards(filter or None)

    @tool(annotations=read_only)
    def litex_board_info(name: str, sections: list[str] = ["Target"]) -> dict:
        """Describe a LiteX-Boards target: FPGA device, platform class and command-line options.

        sections selects option groups of the target (ex: ["Target", "SoC", "Vivado toolchain"]),
        an empty list returns all of them; option_groups lists the available ones.
        """
        return tools.board_info(name, sections)

    @tool(annotations=read_only)
    def litex_list_cpus(filter: str = "") -> list:
        """List the CPUs supported by LiteX (name, family, data width, variants for --cpu-variant)."""
        return tools.list_cpus(filter or None)

    @tool(annotations=read_only)
    def litex_list_cores() -> list:
        """List the LiteX ecosystem cores (LiteDRAM, LiteEth, LitePCIe...) and whether they are installed."""
        return tools.list_cores()

    # Simulation and jobs.
    @tool(annotations=side_effect)
    def litex_sim_start(args: list[str] = [], output_dir: str = "") -> dict:
        """Start a SoC simulation (litex_sim, Verilator) in the background and return its job.

        args are litex_sim options (ex: ["--cpu-type=vexriscv", "--with-sdram"]). The console goes
        to the job log: wait for the BIOS prompt with litex_job_wait(job, "litex>"). To reach the
        SoC bus, add ["--uart-name=crossover+uartbone", "--uart-tcp", "--uart-tcp-port=2345"], then
        litex_server_start(["--uart", "--uart-port=socket://localhost:2345", "--bind-port=1240"])
        and litex_connect(port=1240, csr_csv=<csr_csv of the job>). The first build takes minutes.
        """
        return tools.sim_start(args, output_dir or None)

    @tool(annotations=side_effect)
    def litex_server_start(args: list[str], timeout: float = 300) -> dict:
        """Start a litex_server in the background (ex: ["--uart", "--uart-port=/dev/ttyUSB1"]).

        Refuses a --bind-port already in use; with a socket:// UART port (simulation), first waits
        (up to timeout s) for the simulation to listen.
        """
        return tools.server_start(args, timeout)

    # Console.
    @tool(annotations=side_effect)
    def litex_console_read(timeout: float = 1.0) -> dict:
        """Read the SoC console output (crossover UART) until it stays idle for timeout s (consumes it)."""
        return tools.console_read(timeout)

    if tools.allow_write:
        @tool(annotations=destructive)
        def litex_console_command(command: str, expect: str = "litex>", timeout: float = 10.0) -> dict:
            """Send a command line to the SoC console (ex: BIOS "help", "mem_list") and return the
            output until expect (regex, default: the BIOS prompt) or timeout."""
            return tools.console_command(command, expect, timeout)

    # LiteScope.
    @tool(annotations=read_only)
    def litex_scope_list(analyzer_csv: str = "analyzer.csv") -> dict:
        """List the LiteScope analyzer groups and signals (analyzer.csv of the build), depth, sample rate."""
        return tools.scope_list(analyzer_csv)

    @tool(annotations=side_effect)
    def litex_scope_capture(analyzer_csv: str = "analyzer.csv", group: int = 0, triggers: list[dict] = [],
        offset: int = 32, length: int = 0, subsampling: int = 1, timeout: float = 10,
        signals: list[str] = [], max_changes: int = 32) -> dict:
        """Capture signals with the LiteScope analyzer and return the result as data.

        triggers: [{"signal": "...", "type": "rising"|"falling"|"value", "value": "0x10"}]; no trigger
        captures immediately. offset: samples kept before the trigger; length: samples (0: depth).
        Returns per signal the value at the trigger, the transition count and the first changes
        (sample, value), plus a VCD file of the full capture. Configures the analyzer CSRs only.
        """
        return tools.scope_capture(analyzer_csv, group, triggers, offset, length or None, subsampling,
            timeout, signals or None, max_changes)

    @tool(annotations=side_effect)
    def litex_build_start(target: str, args: list[str] = [], output_dir: str = "", build: bool = True) -> dict:
        """Start a gateware build in the background and return its job.

        target is a LiteX-Boards board name (see litex_list_boards/litex_board_info) or a target script
        (.py); args are its options (ex: ["--cpu-type=vexriscv", "--with-ethernet", "--toolchain=yosys+nextpnr"]).
        Builds take minutes: poll with litex_job_status or litex_job_wait(job, timeout=600), then call
        litex_build_report. --load/--flash need the server to run with --allow-write. The build runs
        from output_dir (a LiteScope analyzer.csv is written there); existing relative paths in args
        are made absolute.
        build=False runs a target script as is, with args only (no --build added): use it for a
        project's own simulation script (it keeps running as a job, stop it with litex_job_stop).
        """
        return tools.build_start(target, args, output_dir or None, build)

    @tool(annotations=read_only)
    def litex_build_report(job: str = "", output_dir: str = "", max_paths: int = 10) -> dict:
        """Structured result of a build (job or output_dir): toolchain, timing met/WNS/TNS, per clock
        results, failing/worst paths, utilization and error lines (Vivado, Quartus, Gowin, Efinity and nextpnr),
        the build_info.json of the build and its LiteScope analyzer.csv (when present)."""
        return tools.build_report(job or None, output_dir or None, max_paths)

    @tool(annotations=read_only)
    def litex_build_info(job: str = "", output_dir: str = "") -> dict:
        """build_info.json of a build (job or output_dir, default: the build of the selected CSR file):
        command line, platform/device/toolchain, CPU, sys_clk_freq, generated files (csr.csv/csr.json,
        bitstream...) and build status (running, succeeded, failed; run=false: generation only)."""
        return tools.build_info(job or None, output_dir or None)

    @tool(annotations=read_only)
    def litex_list_jobs() -> list:
        """List the background jobs (simulations, servers, builds) started by this server."""
        return tools.list_jobs()

    @tool(annotations=read_only)
    def litex_job_status(job: str, tail: int = 40) -> dict:
        """Status of a background job: running, return code, elapsed time, last log lines."""
        return tools.job_status(job, tail)

    @tool(annotations=read_only)
    def litex_job_wait(job: str, pattern: str = "", timeout: float = 60) -> dict:
        """Wait (up to timeout s, max 600) until the job log matches pattern (regex) or the job ends."""
        return tools.job_wait(job, pattern or None, timeout)

    @tool(annotations=side_effect)
    def litex_job_stop(job: str) -> dict:
        """Stop a background job and all its child processes."""
        return tools.job_stop(job)

    # Resources: files describing the SoC of the selected CSR file (read-only).
    def soc_file_reader(name):
        def read() -> str: # No parameters: a static resource (not a URI template).
            try:
                return tools.soc_file(name)
            except LiteXMCPError as e:
                # Message to the client (MCP SDK >= 2 hides it for other exceptions).
                raise _get_resource_error_class()(str(e)) from e
        return read

    for name, mime_type, description in [
        ("csr.csv",         "text/csv",         "CSR map of the SoC (registers, memory regions, constants)."),
        ("csr.json",        "application/json", "CSR map of the SoC in JSON (as csr.csv, with more details)."),
        ("build_info.json", "application/json", "Build of the SoC: command, platform, toolchain, CPU, files, status."),
    ]:
        server.resource(f"litex://soc/{name}", name=name, description=description,
            mime_type=mime_type)(soc_file_reader(name))

    return server

# Run ----------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX MCP server (Model Context Protocol, stdio).")
    parser.add_argument("--csr-csv",     default="csr.csv",   help="CSR configuration file.")
    parser.add_argument("--host",        default="localhost", help="litex_server host address.")
    parser.add_argument("--port",        default=1234,        help="litex_server port.")
    parser.add_argument("--timeout",     default=2.0,         help="Socket timeout (s).")
    parser.add_argument("--allow-write", action="store_true", help="Expose register/memory write tools.")
    parser.add_argument("--jobs-dir",    default=None,        help="Directory for job logs and simulation builds (default: temporary).")
    args = parser.parse_args()

    tools = LiteXMCPTools(
        host        = args.host,
        port        = args.port,
        csr_csv     = args.csr_csv,
        timeout     = args.timeout,
        allow_write = args.allow_write,
        jobs_dir    = args.jobs_dir,
    )
    try:
        server = build_server(tools)
    except LiteXMCPError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    try:
        server.run()
    finally:
        tools.close_all()

if __name__ == "__main__":
    main()
