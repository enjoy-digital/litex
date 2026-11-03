#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Check: build the target of the workspace, verify the BIOS boot log, the main RAM region and the
# main RAM content over the whole region (through the bridge).

import os
import time

from test.agent_eval.common import CheckResult, run_sim_check

AGENT_PORTS   = range(21300, 21350) # Ports given to the agent (UART, litex_server, ...).
UART_PORT     = 21350
SERVER_PORT   = 21351
MAIN_RAM_BASE = 0x40000000
MAIN_RAM_SIZE = 0x10000

def check(workdir):
    result = CheckResult("bios_memtest")

    def body(session):
        # Boot log.
        log   = ""
        start = time.time()
        while "litex>" not in log and (time.time() - start) < 300:
            log += session.console_read(timeout=1.0)
        result.add("bios_prompt", "litex>" in log, log[-300:])
        result.add("bios_memtest", "Memtest OK" in log and "Memory initialization failed" not in log,
            "\n".join(l for l in log.splitlines() if "Memtest" in l or "errors" in l or "failed" in l))

        # Main RAM region.
        region = getattr(session.bus.mems, "main_ram", None)
        result.add("main_ram_region", region is not None and region.base == MAIN_RAM_BASE and
            region.size == MAIN_RAM_SIZE,
            "missing" if region is None else f"base={region.base:#x} size={region.size:#x}")

        # Main RAM content: one distinct word per 1KiB, written then read back.
        addrs = [MAIN_RAM_BASE + offset for offset in range(0, MAIN_RAM_SIZE, 0x400)]
        for i, addr in enumerate(addrs):
            session.bus.write(addr, 0x5a000000 + i)
        errors = [hex(addr) for i, addr in enumerate(addrs) if session.bus.read(addr) != 0x5a000000 + i]
        result.add("main_ram_content", not errors, f"{len(errors)}/{len(addrs)} errors {errors[:4]}")

    return run_sim_check(result, os.path.join(workdir, "target.py"), UART_PORT, SERVER_PORT, body)
