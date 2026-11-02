#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import tempfile
import unittest
import importlib.util

from litex.tools.remote.csr_builder import CSRElements, CSRRegister, CSRMemoryRegion
from litex.tools.litex_mcp import LiteXMCPTools, LiteXMCPError, build_server

# Fake Remote Client -------------------------------------------------------------------------------

IDENT = "LiteX MCP test SoC"

class FakeClient:
    """Minimal RemoteClient stand-in: a word-addressed memory with an identifier and two CSRs."""
    def __init__(self, host, port, csr_csv, timeout, raise_on_timeout):
        self.mem    = {}
        self.opened = False
        self.writes = []
        for i, c in enumerate(IDENT + "\0"):
            self.mem[0xf0001000 + 4*i] = ord(c)
        self.mem[0xf0000004] = 0x12345678
        self.bases     = CSRElements({"identifier_mem": 0xf0001000})
        self.constants = CSRElements({"config_clock_frequency": 100000000, "uart_interrupt": 0})
        self.mems      = CSRElements({"sram": CSRMemoryRegion(0x10000000, 0x2000, "cached")})
        self.regs      = CSRElements({
            "ctrl_scratch"    : CSRRegister(self.read, self.write, "ctrl_scratch",    0xf0000004, 1, 32, "rw"),
            "ctrl_bus_errors" : CSRRegister(self.read, self.write, "ctrl_bus_errors", 0xf0000008, 1, 32, "ro"),
        })

    def open(self):
        self.opened = True

    def close(self):
        self.opened = False

    def read(self, addr, length=None, burst="incr"):
        datas = [self.mem.get(addr + 4*i, 0) for i in range(1 if length is None else length)]
        return datas[0] if length is None else datas

    def write(self, addr, datas, burst="incr"):
        datas = datas if isinstance(datas, list) else [datas]
        for i, data in enumerate(datas):
            self.mem[addr + 4*i] = data
        self.writes.append((addr, datas))

class FakeScopeDriver:
    """LiteScopeAnalyzerDriver stand-in: two signals (stb: 1 bit, adr: 4 bits), stb rises at sample 2."""
    instances = []
    def __init__(self, regs, name, config_csv=None):
        self.calls  = []
        self.offset = 0
        FakeScopeDriver.instances.append(self)
    def configure_group(self, value):       self.calls.append(("group", value))
    def configure_subsampler(self, value):  self.calls.append(("subsampler", value))
    def add_rising_edge_trigger(self, name): self.calls.append(("rising", name))
    def add_falling_edge_trigger(self, name): self.calls.append(("falling", name))
    def add_trigger(self, cond):            self.calls.append(("value", cond))
    def run(self, offset, length):          self.offset = offset
    def done(self):                         return True
    def upload(self):
        stb = [0, 0, 1, 1, 0, 1]
        adr = [0, 0, 3, 4, 4, 5]
        return [s | (a << 1) for s, a in zip(stb, adr)]
    def save(self, filename):
        open(filename, "w").close()

ANALYZER_CSV = """\
config,None,data_width,5
config,None,depth,512
config,None,samplerate,100000000
signal,0,stb,1
signal,0,adr,4
"""

class FakeConsoleClient(FakeClient):
    """FakeClient with a crossover UART: echoes the command, answers "help" with a line and a prompt."""
    RXTX, RXEMPTY, RXFULL = 0xf0002000, 0xf0002004, 0xf0002008
    def __init__(self, *args, **kwargs):
        FakeClient.__init__(self, *args, **kwargs)
        self.rx   = list(b"BIOS booted\nlitex> ")
        self.line = ""
        for name, addr in [("rxtx", self.RXTX), ("rxempty", self.RXEMPTY), ("rxfull", self.RXFULL)]:
            self.regs.d[f"uart_xover_{name}"] = CSRRegister(self.read, self.write, f"uart_xover_{name}", addr, 1, 32, "rw")

    def read(self, addr, length=None, burst="incr"):
        if addr == self.RXEMPTY:
            return int(len(self.rx) == 0)
        if addr == self.RXFULL:
            return int(len(self.rx) >= 16)
        if addr == self.RXTX:
            n = 1 if length is None else length
            datas, self.rx = self.rx[:n], self.rx[n:]
            return datas[0] if length is None else datas
        return FakeClient.read(self, addr, length, burst)

    def write(self, addr, datas, burst="incr"):
        if addr == self.RXTX:
            c = chr((datas if isinstance(datas, int) else datas[0]) & 0xff)
            self.rx.append(ord(c))
            if c == "\n":
                if self.line == "help":
                    self.rx += list(b"LiteX BIOS, available commands:\n" + b"x"*40 + b"\nlitex> ")
                self.line = ""
            else:
                self.line += c
            return
        FakeClient.write(self, addr, datas, burst)

def _tools(**kwargs):
    return LiteXMCPTools(csr_csv=None, client_cls=FakeClient, **kwargs)

# Fake MCP Server ----------------------------------------------------------------------------------

class FakeServer:
    """Records the tools registered by build_server (MCP SDK not required)."""
    def __init__(self, name, instructions=None):
        self.name         = name
        self.instructions = instructions
        self.tools        = {}
        self.annotations  = {}

    def tool(self, annotations=None):
        def register(fn):
            self.tools[fn.__name__]       = fn
            self.annotations[fn.__name__] = annotations
            return fn
        return register

# Test LiteX MCP -----------------------------------------------------------------------------------

class TestLiteXMCP(unittest.TestCase):
    def test_ident_and_check(self):
        tools = _tools()
        self.assertEqual(tools.ident(), IDENT)
        check = tools.check()
        self.assertEqual(check["ident"],        IDENT)
        self.assertEqual(check["ctrl_scratch"], "0x12345678")
        self.assertFalse(check["allow_write"])

    def test_list_and_read(self):
        tools = _tools()
        self.assertEqual([r["name"] for r in tools.list_registers("ctrl_s")], ["ctrl_scratch"])
        self.assertEqual(tools.list_memory_regions()[0]["name"], "sram")
        self.assertEqual(tools.list_constants("uart"), {"uart_interrupt": 0})
        self.assertEqual(tools.read_register("ctrl_scratch")["value"], 0x12345678)
        self.assertEqual(len(tools.read_registers("ctrl_")), 2)
        self.assertEqual(tools.read_memory(0xf0000004, 2)["words"], ["0x12345678", "0x00000000"])

    def test_errors(self):
        tools = _tools()
        with self.assertRaises(LiteXMCPError):
            tools.read_register("unknown")
        with self.assertRaises(LiteXMCPError):
            tools.read_memory(0, 0)
        with self.assertRaises(LiteXMCPError):
            LiteXMCPTools(csr_csv="does_not_exist.csv", client_cls=FakeClient).ident()

    def test_writes_need_allow_write(self):
        tools = _tools()
        with self.assertRaises(LiteXMCPError):
            tools.write_register("ctrl_scratch", 1)
        with self.assertRaises(LiteXMCPError):
            tools.write_memory(0x10000000, [1])
        self.assertEqual(tools._get_bus().writes, [])

        tools = _tools(allow_write=True)
        tools.write_register("ctrl_scratch", 0xcafe)
        tools.write_memory(0x10000000, [1, 2])
        self.assertEqual(tools.read_register("ctrl_scratch")["value"], 0xcafe)
        self.assertEqual(tools.read_memory(0x10000000, 2)["words"], ["0x00000001", "0x00000002"])

    def test_connect(self):
        tools = _tools()
        tools.ident()
        self.assertEqual(tools.connect(port=1240)["port"], 1240)
        self.assertEqual(tools.port, 1240)

    def test_list_cpus(self):
        cpus = {c["name"]: c for c in _tools().list_cpus("vexriscv")}
        self.assertIn("vexriscv", cpus)
        self.assertIn("standard", cpus["vexriscv"]["variants"])

    def test_list_cores(self):
        cores = {c["name"]: c for c in _tools().list_cores()}
        self.assertIn("litedram", cores)

    @unittest.skipIf(importlib.util.find_spec("litex_boards") is None, "LiteX-Boards not installed.")
    def test_boards(self):
        tools = _tools()
        self.assertIn("digilent_arty", [b["name"] for b in tools.list_boards("arty")])
        info = tools.board_info("digilent_arty")
        self.assertEqual(info["platform_class"], "Xilinx7SeriesPlatform")
        self.assertIn("a7-35", info["devices"])
        self.assertIn("--variant", info["options"]["Target"])
        with self.assertRaises(LiteXMCPError):
            tools.board_info("../setup")

    def test_jobs(self):
        with tempfile.TemporaryDirectory() as d:
            tools = _tools(jobs_dir=d)
            # A job printing a prompt then waiting, as a simulation does.
            script = "import time; print('BIOS built', flush=True); print('litex> ', flush=True); time.sleep(60)"
            job = tools._start_job("test", [sys.executable, "-c", script])["job"]
            r = tools.job_wait(job, r"litex>", timeout=30)
            self.assertEqual(r["matched"], "litex>")
            self.assertTrue(r["running"])
            self.assertIn("BIOS built", r["log_tail"])
            r = tools.job_wait(job, r"never printed", timeout=0.5)
            self.assertTrue(r["timeout"])
            self.assertFalse(tools.job_stop(job)["running"])
            self.assertEqual([j["job"] for j in tools.list_jobs()], [job])

            # A job that ends: wait returns on exit with the return code.
            job = tools._start_job("test", [sys.executable, "-c", "import sys; sys.exit(3)"])["job"]
            r = tools.job_wait(job, timeout=30)
            self.assertEqual(r["returncode"], 3)
            self.assertFalse(r["timeout"])

            with self.assertRaises(LiteXMCPError):
                tools.job_status("unknown")
            with self.assertRaises(LiteXMCPError):
                tools._start_job("test", "rm -rf /")

    def test_sim_command(self):
        with tempfile.TemporaryDirectory() as d:
            tools = _tools(jobs_dir=d)
            calls = []
            tools._start_job = lambda kind, cmd, cwd=None, info=None: calls.append((kind, cmd, info)) or info
            info = tools.sim_start(["--with-sdram"])
            kind, cmd, _ = calls[0]
            self.assertEqual(kind, "sim")
            self.assertEqual(cmd[1:3], ["-m", "litex.tools.litex_sim"])
            self.assertIn("--non-interactive", cmd)
            self.assertEqual(cmd[-1], "--with-sdram")
            self.assertEqual(info["csr_csv"], os.path.join(info["output_dir"], "csr.csv"))

    def test_build(self):
        with tempfile.TemporaryDirectory() as d:
            tools = _tools(jobs_dir=d)
            calls = []
            tools._start_job = lambda kind, cmd, cwd=None, info=None: calls.append((kind, cmd)) or info
            target = os.path.join(d, "target.py")
            with open(target, "w") as f:
                f.write("")
            info = tools.build_start(target, ["--cpu-type=vexriscv", "--build"])
            kind, cmd = calls[0]
            self.assertEqual(kind, "build")
            self.assertEqual(cmd[1], target)
            self.assertEqual(cmd.count("--build"), 1)
            self.assertIn(f"--output-dir={info['output_dir']}", cmd)
            # Loading/flashing a board is a hardware side effect.
            with self.assertRaises(LiteXMCPError):
                tools.build_start(target, ["--load"])
            with self.assertRaises(LiteXMCPError):
                tools.build_start(os.path.join(d, "missing.py"))
            # Report of a build directory.
            os.makedirs(os.path.join(info["output_dir"], "gateware"))
            with open(os.path.join(info["output_dir"], "litex.log"), "w") as f:
                f.write("ERROR: something failed.\n")
            self.assertEqual(tools.build_report(output_dir=info["output_dir"])["errors"], ["ERROR: something failed."])
            with self.assertRaises(LiteXMCPError):
                tools.build_report(output_dir=os.path.join(d, "missing"))

    def test_scope(self):
        with tempfile.TemporaryDirectory() as d:
            csv = os.path.join(d, "analyzer.csv")
            with open(csv, "w") as f:
                f.write(ANALYZER_CSV)
            tools = _tools(jobs_dir=d)
            l = tools.scope_list(csv)
            self.assertEqual(l["depth"], 512)
            self.assertEqual(l["groups"][0], [{"name": "stb", "width": 1}, {"name": "adr", "width": 4}])

            # No analyzer in the SoC.
            with self.assertRaises(LiteXMCPError):
                tools.scope_capture(csv)

            # Capture with a fake driver.
            bus = tools._get_bus()
            bus.regs.d["analyzer_mux_value"] = None
            tools._scope_driver_class = lambda: FakeScopeDriver
            r = tools.scope_capture(csv, triggers=[{"signal": "stb", "type": "rising"}], offset=2)
            self.assertTrue(r["triggered"])
            self.assertEqual(FakeScopeDriver.instances[-1].calls[-1], ("rising", "stb"))
            self.assertEqual(r["signals"]["stb"]["at_trigger"],  "0x1")
            self.assertEqual(r["signals"]["stb"]["transitions"], 3)
            self.assertEqual(r["signals"]["adr"]["changes"][:2], [[0, "0x0"], [2, "0x3"]])
            self.assertTrue(os.path.exists(r["vcd"]))
            with self.assertRaises(LiteXMCPError):
                tools.scope_capture(csv, triggers=[{"signal": "unknown"}])

    def test_console(self):
        tools = LiteXMCPTools(csr_csv=None, client_cls=FakeConsoleClient)
        self.assertIn("BIOS booted", tools.console_read(timeout=0.2)["output"])
        with self.assertRaises(LiteXMCPError):
            tools.console_command("help")
        tools = LiteXMCPTools(csr_csv=None, client_cls=FakeConsoleClient, allow_write=True)
        r = tools.console_command("help", timeout=5)
        self.assertTrue(r["matched"])
        self.assertIn("available commands", r["output"])
        with self.assertRaises(LiteXMCPError):
            _tools().console_read() # No crossover UART.

    def test_server_tools(self):
        read_tools = {
            "litex_check", "litex_ident", "litex_list_registers",
            "litex_list_memory_regions", "litex_list_constants", "litex_read_register",
            "litex_read_registers", "litex_read_memory", "litex_list_boards", "litex_board_info",
            "litex_list_cpus", "litex_list_cores", "litex_list_jobs", "litex_job_status",
            "litex_job_wait", "litex_build_report", "litex_scope_list",
        }
        side_effect_tools = {"litex_connect", "litex_sim_start", "litex_server_start", "litex_job_stop",
            "litex_build_start", "litex_scope_capture", "litex_console_read"}
        write_tools = {"litex_write_register", "litex_write_memory", "litex_console_command"}

        server = build_server(_tools(), server_cls=FakeServer)
        self.assertEqual(set(server.tools), read_tools | side_effect_tools)
        self.assertEqual(server.tools["litex_ident"](), IDENT)

        server = build_server(_tools(allow_write=True), server_cls=FakeServer)
        self.assertEqual(set(server.tools), read_tools | side_effect_tools | write_tools)

        # Read-only/destructive hints (when the MCP SDK is installed).
        if importlib.util.find_spec("mcp") is not None:
            hints = lambda a: a.model_dump(by_alias=True) # SDK 1.x/2.x field names differ, aliases do not.
            self.assertTrue(hints(server.annotations["litex_read_register"])["readOnlyHint"])
            self.assertTrue(hints(server.annotations["litex_write_register"])["destructiveHint"])

if __name__ == "__main__":
    unittest.main()
