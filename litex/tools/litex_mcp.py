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
import sys
import time
import argparse

from litex.tools.litex_client import RemoteClient

# Helpers ------------------------------------------------------------------------------------------

MAX_READ_WORDS = 4096

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
        client_cls=RemoteClient):
        self.host        = host
        self.port        = int(port)
        self.csr_csv     = csr_csv
        self.timeout     = float(timeout)
        self.allow_write = allow_write
        self.client_cls  = client_cls
        self.bus         = None

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

# MCP Server ---------------------------------------------------------------------------------------

INSTRUCTIONS = """\
Tools to observe (and optionally control) a running LiteX SoC through litex_server.
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

def build_server(tools, server_cls=None):
    server_cls = _get_server_class() if server_cls is None else server_cls
    server     = server_cls("litex", instructions=INSTRUCTIONS)

    # Read tools.
    @server.tool()
    def litex_check() -> dict:
        """Check the link to the SoC: identifier, CSR read round-trip latency, write permission."""
        return tools.check()

    @server.tool()
    def litex_ident() -> str:
        """Return the identifier string of the SoC."""
        return tools.ident()

    @server.tool()
    def litex_list_registers(filter: str = "") -> list:
        """List the SoC CSRs (name, address, size in CSR words, mode), optionally filtered by a name substring."""
        return tools.list_registers(filter or None)

    @server.tool()
    def litex_list_memory_regions() -> list:
        """List the SoC memory regions (name, base, size, type)."""
        return tools.list_memory_regions()

    @server.tool()
    def litex_list_constants(filter: str = "") -> dict:
        """List the SoC constants (configuration, interrupts...), optionally filtered by a name substring."""
        return tools.list_constants(filter or None)

    @server.tool()
    def litex_read_register(name: str) -> dict:
        """Read a CSR by its csr.csv name (ex: ctrl_scratch)."""
        return tools.read_register(name)

    @server.tool()
    def litex_read_registers(filter: str) -> list:
        """Read every readable CSR whose name contains filter (ex: "uart_")."""
        return tools.read_registers(filter)

    @server.tool()
    def litex_read_memory(address: int, length: int = 1) -> dict:
        """Read length 32-bit words from the SoC main bus at address."""
        return tools.read_memory(address, length)

    # Write tools (only exposed with --allow-write).
    if tools.allow_write:
        @server.tool()
        def litex_write_register(name: str, value: int) -> dict:
            """Write a CSR by its csr.csv name."""
            return tools.write_register(name, value)

        @server.tool()
        def litex_write_memory(address: int, words: list[int]) -> dict:
            """Write 32-bit words to the SoC main bus at address."""
            return tools.write_memory(address, words)

    return server

# Run ----------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX MCP server (Model Context Protocol, stdio).")
    parser.add_argument("--csr-csv",     default="csr.csv",   help="CSR configuration file.")
    parser.add_argument("--host",        default="localhost", help="litex_server host address.")
    parser.add_argument("--port",        default=1234,        help="litex_server port.")
    parser.add_argument("--timeout",     default=2.0,         help="Socket timeout (s).")
    parser.add_argument("--allow-write", action="store_true", help="Expose register/memory write tools.")
    args = parser.parse_args()

    tools = LiteXMCPTools(
        host        = args.host,
        port        = args.port,
        csr_csv     = args.csr_csv,
        timeout     = args.timeout,
        allow_write = args.allow_write,
    )
    try:
        server = build_server(tools)
    except LiteXMCPError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    try:
        server.run()
    finally:
        tools.close()

if __name__ == "__main__":
    main()
