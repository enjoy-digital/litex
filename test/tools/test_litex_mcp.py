#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

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

    def test_server_tools(self):
        read_tools = {
            "litex_check", "litex_connect", "litex_ident", "litex_list_registers",
            "litex_list_memory_regions", "litex_list_constants", "litex_read_register",
            "litex_read_registers", "litex_read_memory", "litex_list_boards", "litex_board_info",
            "litex_list_cpus", "litex_list_cores",
        }
        write_tools = {"litex_write_register", "litex_write_memory"}

        server = build_server(_tools(), server_cls=FakeServer)
        self.assertEqual(set(server.tools), read_tools)
        self.assertEqual(server.tools["litex_ident"](), IDENT)

        server = build_server(_tools(allow_write=True), server_cls=FakeServer)
        self.assertEqual(set(server.tools), read_tools | write_tools)

        # Read-only/destructive hints (when the MCP SDK is installed).
        if importlib.util.find_spec("mcp") is not None:
            hints = lambda a: a.model_dump(by_alias=True) # SDK 1.x/2.x field names differ, aliases do not.
            self.assertTrue(hints(server.annotations["litex_read_register"])["readOnlyHint"])
            self.assertTrue(hints(server.annotations["litex_write_register"])["destructiveHint"])

if __name__ == "__main__":
    unittest.main()
