#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# End-to-end litex_mcp test: an MCP client (MCP SDK) starts litex_mcp over stdio, which simulates a
# SoC (litex_sim, Verilator), starts a litex_server on it and reads/writes CSRs and the BIOS console.
# Builds a simulation (about a minute): only runs with LITEX_MCP_SIM_TEST=1.

import os
import sys
import json
import time
import socket
import shutil
import asyncio
import tempfile
import unittest
import importlib.util

# Helpers ------------------------------------------------------------------------------------------

def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]

async def _call(session, tool, **kwargs):
    r    = (await session.call_tool(tool, kwargs)).model_dump(by_alias=True) # SDK 1.x/2.x field names differ, aliases do not.
    text = "\n".join(c.get("text", "") for c in r["content"])
    if r.get("isError"):
        raise AssertionError(f"{tool} failed: {text}")
    return json.loads(text)

# Test LiteX MCP Simulation ------------------------------------------------------------------------

@unittest.skipUnless(os.getenv("LITEX_MCP_SIM_TEST") == "1", "Set LITEX_MCP_SIM_TEST=1 to run.")
@unittest.skipIf(importlib.util.find_spec("mcp") is None, "MCP SDK not installed.")
@unittest.skipIf(shutil.which("verilator") is None, "Verilator not installed.")
class TestLiteXMCPSim(unittest.TestCase):
    def test_sim(self):
        asyncio.run(self._test_sim())

    async def _test_sim(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        uart_port   = _free_port()
        server_port = _free_port()
        with tempfile.TemporaryDirectory() as d:
            params = StdioServerParameters(
                command = sys.executable,
                args    = ["-m", "litex.tools.litex_mcp", "--allow-write", f"--jobs-dir={d}"],
                env     = dict(os.environ),
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = [t.name for t in (await session.list_tools()).tools]
                    self.assertIn("litex_sim_start",      tools)
                    self.assertIn("litex_write_register", tools)

                    # Simulated SoC with the CSR bus (UARTBone) and the console (crossover) on TCP.
                    sim = await _call(session, "litex_sim_start", args=[
                        "--cpu-type=vexriscv",
                        "--uart-name=crossover+uartbone",
                        "--uart-tcp",
                        f"--uart-tcp-port={uart_port}",
                    ])
                    server = None
                    try:
                        # Wait for the simulation to be built and to listen on its UART TCP port.
                        from litex.tools.litex_mcp import _tcp_listening
                        for i in range(600):
                            if _tcp_listening(uart_port):
                                break
                            status = await _call(session, "litex_job_status", job=sim["job"], tail=0)
                            if not status["running"]:
                                raise AssertionError(f"Simulation exited (return code {status['returncode']}).")
                            await asyncio.sleep(1)
                        server = await _call(session, "litex_server_start", args=[
                            "--uart",
                            f"--uart-port=socket://localhost:{uart_port}",
                            f"--bind-port={server_port}",
                        ], timeout=60)
                        # litex_server is started in the background: retry until it accepts the connection.
                        start = time.time()
                        while True:
                            try:
                                check = await _call(session, "litex_connect", port=server_port,
                                    csr_csv=sim["csr_csv"], timeout=30)
                                break
                            except AssertionError:
                                if (time.time() - start) > 120:
                                    raise
                                await asyncio.sleep(1)
                        self.assertIn("LiteX", check["ident"])

                        # CSRs.
                        r = await _call(session, "litex_read_register", name="ctrl_scratch")
                        self.assertEqual(r["value"], 0x12345678)
                        await _call(session, "litex_write_register", name="ctrl_scratch", value=0xcafe)
                        r = await _call(session, "litex_read_register", name="ctrl_scratch")
                        self.assertEqual(r["value"], 0xcafe)

                        # BIOS console (crossover UART).
                        await _call(session, "litex_console_read", timeout=5)
                        r = await _call(session, "litex_console_command", command="help", timeout=120)
                        self.assertTrue(r["matched"], r["output"])
                        self.assertIn("help", r["output"])

                        # Build information of the simulation (when supported by litex_mcp).
                        if "litex_build_info" in tools:
                            info = await _call(session, "litex_build_info", job=sim["job"])
                            self.assertEqual(info["platform"]["name"], "sim")
                            self.assertEqual(info["soc"]["cpu_type"],  "vexriscv")
                    except AssertionError:
                        # Status and log tails of the jobs (simulation, litex_server) for the CI log.
                        for job in [sim["job"]] + ([] if server is None else [server["job"]]):
                            status = await _call(session, "litex_job_status", job=job, tail=0)
                            print(f"{job}: running={status['running']} returncode={status['returncode']} "
                                f"elapsed={status['elapsed_s']}s")
                            with open(status["log"], encoding="utf-8", errors="replace") as f:
                                lines = f.read().splitlines()
                            print("\n".join(lines[:30] + ["..."] + lines[-30:] if len(lines) > 60 else lines))
                        raise

if __name__ == "__main__":
    unittest.main()
