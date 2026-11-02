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
import sys
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
            self.bus.close()
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
        """List the CSRs (name, address, size in CSR words, mode); filter is a name substring."""
        regs = []
        for name, reg in self._get_csr("regs").__dict__.items():
            if filter is None or filter in name:
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
        """List the SoC constants (config_*, *_interrupt...); filter is a name substring."""
        constants = self._get_csr("constants")
        return {k: v for k, v in constants.d.items() if filter is None or filter in k}

    # Reads ----------------------------------------------------------------------------------------

    def read_register(self, name):
        """Read a CSR by name."""
        reg   = self._get_register(name)
        value = reg.read()
        return {"name": name, "address": _hex(reg.addr), "value": value, "value_hex": f"0x{value:x}"}

    def read_registers(self, filter):
        """Read every CSR whose name contains filter."""
        return [self.read_register(r["name"]) for r in self.list_registers(filter) if r["mode"] in ["rw", "ro"]]

    def read_memory(self, address, length=1):
        """Read length 32-bit words at address (incrementing burst)."""
        length = int(length)
        if not (0 < length <= MAX_READ_WORDS):
            raise LiteXMCPError(f"length must be between 1 and {MAX_READ_WORDS} words.")
        bus   = self._get_bus()
        datas = bus.read(int(address), length, burst="incr")
        return {"address": _hex(int(address)), "words": [_hex(d) for d in datas]}

    # Writes (--allow-write) -----------------------------------------------------------------------

    def write_register(self, name, value):
        """Write a CSR by name (requires --allow-write)."""
        self._check_write()
        reg = self._get_register(name)
        reg.write(int(value))
        return {"name": name, "address": _hex(reg.addr), "value": int(value)}

    def write_memory(self, address, words):
        """Write 32-bit words at address (incrementing burst, requires --allow-write)."""
        self._check_write()
        words = [int(w) for w in words]
        if not (0 < len(words) <= MAX_READ_WORDS):
            raise LiteXMCPError(f"between 1 and {MAX_READ_WORDS} words can be written.")
        bus = self._get_bus()
        bus.write(int(address), words, burst="incr")
        return {"address": _hex(int(address)), "length": len(words)}

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
        """List the LiteX-Boards targets (name, vendor); filter is a name substring."""
        boards = []
        for f in sorted(os.listdir(self._boards_dir())):
            name = f[:-3]
            if not f.endswith(".py") or name.startswith("_"):
                continue
            if filter is None or filter in name:
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
            if filter is None or filter in name:
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

    def console_command(self, command, expect="litex>", timeout=10.0, max_bytes=16384):
        """Send a command line to the SoC console (ex: a BIOS command) and read until expect (regex)."""
        self._check_write()
        rxtx, rxempty = self._xover()
        self._console_drain(rxtx, rxempty, max_bytes) # Discard pending output.
        for c in command + "\n":
            rxtx.write(ord(c))
        data  = bytearray()
        regex = re.compile(expect) if expect else None
        start = time.time()
        while (time.time() - start) < min(float(timeout), MAX_WAIT_TIME) and len(data) < int(max_bytes):
            chunk = self._console_drain(rxtx, rxempty, int(max_bytes) - len(data))
            data += chunk
            text  = _strip_ansi(data.decode("utf-8", errors="replace"))
            # Match after the echoed command line.
            if regex is not None and regex.search(text.split("\n", 1)[-1] if "\n" in text else ""):
                return {"output": text, "matched": True}
            if not chunk:
                time.sleep(0.05)
        return {"output": _strip_ansi(data.decode("utf-8", errors="replace")), "matched": False}

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

    def build_start(self, target, args=None, output_dir=None):
        """Start a target build (--build) in the background; target is a LiteX-Boards board name or
        a target script (.py). --load/--flash (hardware side effects) require --allow-write."""
        args = [] if args is None else list(args)
        if any(a.split("=")[0] in ["--load", "--flash"] for a in args) and not self.allow_write:
            raise LiteXMCPError("--load/--flash act on the hardware, restart the server with --allow-write.")
        if target.endswith(".py"):
            if not os.path.exists(target):
                raise LiteXMCPError(f"Target script {target} not found.")
            cmd = [sys.executable, os.path.abspath(target)]
        else:
            self.board_info(target, sections=[]) # Validates the board name.
            cmd = [sys.executable, "-m", f"litex_boards.targets.{target}"]
        output_dir = os.path.abspath(output_dir or os.path.join(self._get_jobs_dir(), f"build{len(self.jobs)}"))
        cmd += ["--build", f"--output-dir={output_dir}"] + [a for a in args if a != "--build"]
        return self._start_job("build", cmd, info={
            "output_dir" : output_dir,
            "csr_csv"    : os.path.join(output_dir, "csr.csv"),
        })

    def build_report(self, job=None, output_dir=None, max_paths=10):
        """Timing (WNS/TNS, per clock, failing paths), utilization and errors of a build."""
        if job:
            info       = self._get_job(job)["info"]
            output_dir = info.get("output_dir")
        if not output_dir or not os.path.isdir(output_dir):
            raise LiteXMCPError("Build output directory not found (give a build job or an output_dir).")
        r = parse_build_reports(output_dir, max_paths=int(max_paths))
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
        return self._start_job("server", cmd, info={"bind_port": bind_port})

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

def _tool_annotations(read_only, destructive=False):
    # MCP tool hints: clients can run read-only tools freely and ask for approval on the others.
    try:
        from mcp.types import ToolAnnotations
    except ImportError:
        return None
    return ToolAnnotations.model_validate({"readOnlyHint": read_only, "destructiveHint": destructive})

def build_server(tools, server_cls=None):
    server_cls  = _get_server_class() if server_cls is None else server_cls
    server      = server_cls("litex", instructions=INSTRUCTIONS)
    read_only   = _tool_annotations(read_only=True)
    side_effect = _tool_annotations(read_only=False, destructive=False)
    destructive = _tool_annotations(read_only=False, destructive=True)

    # Connection.
    @server.tool(annotations=read_only)
    def litex_check() -> dict:
        """Check the link to the SoC: identifier, CSR read round-trip latency, write permission."""
        return tools.check()

    @server.tool(annotations=side_effect)
    def litex_connect(host: str = "", port: int = 0, csr_csv: str = "", timeout: float = 0) -> dict:
        """Select another litex_server (host/port) and/or CSR file (ex: a simulation), then check it.
        timeout (s) is the bus access timeout, to raise on slow links (ex: 10 for a simulation)."""
        return tools.connect(host or None, port or None, csr_csv or None, timeout or None)

    # SoC (read).
    @server.tool(annotations=read_only)
    def litex_ident() -> str:
        """Return the identifier string of the SoC."""
        return tools.ident()

    @server.tool(annotations=read_only)
    def litex_list_registers(filter: str = "") -> list:
        """List the SoC CSRs (name, address, size in CSR words, mode), optionally filtered by a name substring."""
        return tools.list_registers(filter or None)

    @server.tool(annotations=read_only)
    def litex_list_memory_regions() -> list:
        """List the SoC memory regions (name, base, size, type)."""
        return tools.list_memory_regions()

    @server.tool(annotations=read_only)
    def litex_list_constants(filter: str = "") -> dict:
        """List the SoC constants (configuration, interrupts...), optionally filtered by a name substring."""
        return tools.list_constants(filter or None)

    @server.tool(annotations=read_only)
    def litex_read_register(name: str) -> dict:
        """Read a CSR by its csr.csv name (ex: ctrl_scratch)."""
        return tools.read_register(name)

    @server.tool(annotations=read_only)
    def litex_read_registers(filter: str) -> list:
        """Read every readable CSR whose name contains filter (ex: "uart_")."""
        return tools.read_registers(filter)

    @server.tool(annotations=read_only)
    def litex_read_memory(address: int, length: int = 1) -> dict:
        """Read length 32-bit words from the SoC main bus at address."""
        return tools.read_memory(address, length)

    # SoC (write, only exposed with --allow-write).
    if tools.allow_write:
        @server.tool(annotations=destructive)
        def litex_write_register(name: str, value: int) -> dict:
            """Write a CSR by its csr.csv name."""
            return tools.write_register(name, value)

        @server.tool(annotations=destructive)
        def litex_write_memory(address: int, words: list[int]) -> dict:
            """Write 32-bit words to the SoC main bus at address."""
            return tools.write_memory(address, words)

    # Introspection (no board needed).
    @server.tool(annotations=read_only)
    def litex_list_boards(filter: str = "") -> list:
        """List the LiteX-Boards targets (name, vendor), optionally filtered by a name substring (ex: "arty")."""
        return tools.list_boards(filter or None)

    @server.tool(annotations=read_only)
    def litex_board_info(name: str, sections: list[str] = ["Target"]) -> dict:
        """Describe a LiteX-Boards target: FPGA device, platform class and command-line options.

        sections selects option groups of the target (ex: ["Target", "SoC", "Vivado toolchain"]),
        an empty list returns all of them; option_groups lists the available ones.
        """
        return tools.board_info(name, sections)

    @server.tool(annotations=read_only)
    def litex_list_cpus(filter: str = "") -> list:
        """List the CPUs supported by LiteX (name, family, data width, variants for --cpu-variant)."""
        return tools.list_cpus(filter or None)

    @server.tool(annotations=read_only)
    def litex_list_cores() -> list:
        """List the LiteX ecosystem cores (LiteDRAM, LiteEth, LitePCIe...) and whether they are installed."""
        return tools.list_cores()

    # Simulation and jobs.
    @server.tool(annotations=side_effect)
    def litex_sim_start(args: list[str] = [], output_dir: str = "") -> dict:
        """Start a SoC simulation (litex_sim, Verilator) in the background and return its job.

        args are litex_sim options (ex: ["--cpu-type=vexriscv", "--with-sdram"]). The console goes
        to the job log: wait for the BIOS prompt with litex_job_wait(job, "litex>"). To reach the
        SoC bus, add ["--uart-name=crossover+uartbone", "--uart-tcp", "--uart-tcp-port=2345"], then
        litex_server_start(["--uart", "--uart-port=socket://localhost:2345", "--bind-port=1240"])
        and litex_connect(port=1240, csr_csv=<csr_csv of the job>). The first build takes minutes.
        """
        return tools.sim_start(args, output_dir or None)

    @server.tool(annotations=side_effect)
    def litex_server_start(args: list[str], timeout: float = 300) -> dict:
        """Start a litex_server in the background (ex: ["--uart", "--uart-port=/dev/ttyUSB1"]).

        Refuses a --bind-port already in use; with a socket:// UART port (simulation), first waits
        (up to timeout s) for the simulation to listen.
        """
        return tools.server_start(args, timeout)

    # Console.
    @server.tool(annotations=side_effect)
    def litex_console_read(timeout: float = 1.0) -> dict:
        """Read the SoC console output (crossover UART) until it stays idle for timeout s (consumes it)."""
        return tools.console_read(timeout)

    if tools.allow_write:
        @server.tool(annotations=destructive)
        def litex_console_command(command: str, expect: str = "litex>", timeout: float = 10.0) -> dict:
            """Send a command line to the SoC console (ex: BIOS "help", "mem_list") and return the
            output until expect (regex, default: the BIOS prompt) or timeout."""
            return tools.console_command(command, expect, timeout)

    # LiteScope.
    @server.tool(annotations=read_only)
    def litex_scope_list(analyzer_csv: str = "analyzer.csv") -> dict:
        """List the LiteScope analyzer groups and signals (analyzer.csv of the build), depth, sample rate."""
        return tools.scope_list(analyzer_csv)

    @server.tool(annotations=side_effect)
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

    @server.tool(annotations=side_effect)
    def litex_build_start(target: str, args: list[str] = [], output_dir: str = "") -> dict:
        """Start a gateware build in the background and return its job.

        target is a LiteX-Boards board name (see litex_list_boards/litex_board_info) or a target script
        (.py); args are its options (ex: ["--cpu-type=vexriscv", "--with-ethernet", "--toolchain=yosys+nextpnr"]).
        Builds take minutes: poll with litex_job_status or litex_job_wait(job, timeout=600), then call
        litex_build_report. --load/--flash need the server to run with --allow-write.
        """
        return tools.build_start(target, args, output_dir or None)

    @server.tool(annotations=read_only)
    def litex_build_report(job: str = "", output_dir: str = "", max_paths: int = 10) -> dict:
        """Structured result of a build (job or output_dir): toolchain, timing met/WNS/TNS, per clock
        results, failing/worst paths, utilization and error lines. Vivado, Quartus, Gowin, Efinity and nextpnr."""
        return tools.build_report(job or None, output_dir or None, max_paths)

    @server.tool(annotations=read_only)
    def litex_list_jobs() -> list:
        """List the background jobs (simulations, servers, builds) started by this server."""
        return tools.list_jobs()

    @server.tool(annotations=read_only)
    def litex_job_status(job: str, tail: int = 40) -> dict:
        """Status of a background job: running, return code, elapsed time, last log lines."""
        return tools.job_status(job, tail)

    @server.tool(annotations=read_only)
    def litex_job_wait(job: str, pattern: str = "", timeout: float = 60) -> dict:
        """Wait (up to timeout s, max 600) until the job log matches pattern (regex) or the job ends."""
        return tools.job_wait(job, pattern or None, timeout)

    @server.tool(annotations=side_effect)
    def litex_job_stop(job: str) -> dict:
        """Stop a background job and all its child processes."""
        return tools.job_stop(job)

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
