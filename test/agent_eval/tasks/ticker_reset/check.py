#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Check: build the target of the workspace and verify the ticker against its specification,
# without any write to the control register before the first delay.

import os
import time

from test.agent_eval.common import CheckResult, run_sim_check

TIER        = "v1"            # Fault visible in the source.
AGENT_PORTS = range(21100, 21150) # Ports given to the agent (UART, litex_server, ...).
UART_PORT   = 21150
SERVER_PORT = 21151

def _wait_zero(regs, timeout, stall_timeout=5):
    # Wait for status.zero, give up when the counter does not move for stall_timeout s.
    start = last = time.time()
    value = regs.ticker_value.read()
    while not (regs.ticker_status.read() & 0x1):
        if regs.ticker_value.read() != value:
            value = regs.ticker_value.read()
            last  = time.time()
        if (time.time() - start) > timeout or (time.time() - last) > stall_timeout:
            return False
        time.sleep(0.01)
    return True

def check(workdir):
    result = CheckResult("ticker_reset")

    def body(session):
        regs  = session.bus.regs
        names = [n for n in regs.d.keys() if n.startswith("ticker_")]
        result.add("register_map", names == ["ticker_control", "ticker_prescaler", "ticker_load",
            "ticker_value", "ticker_status"], names)
        result.add("reset_values", (regs.ticker_control.read() & 0x3) == 0x1 and
            regs.ticker_prescaler.read() == 999,
            f"control={regs.ticker_control.read():#x} prescaler={regs.ticker_prescaler.read()}")

        # One-shot delay out of reset: counts down and stops at 0.
        regs.ticker_load.write(100)
        v0 = regs.ticker_value.read()
        result.add("one_shot", _wait_zero(regs, timeout=60) and regs.ticker_value.read() == 0,
            f"first value {v0}, value {regs.ticker_value.read()}")

        # Disabled: the counter holds.
        regs.ticker_control.write(0)
        regs.ticker_load.write(50)
        time.sleep(0.5)
        result.add("disable", regs.ticker_value.read() == 50, f"value {regs.ticker_value.read()}")

        # Periodic mode with a faster tick: the counter reloads at 0.
        regs.ticker_prescaler.write(9)
        regs.ticker_control.write(0x3)
        values = [regs.ticker_value.read()]
        start  = time.time()
        while (time.time() - start) < 20 and not (len(values) > 3 and values[-1] > values[-2]):
            values.append(regs.ticker_value.read())
        result.add("periodic", len(values) > 3 and values[-1] > values[-2] and max(values) <= 50,
            values[-8:])

    return run_sim_check(result, os.path.join(workdir, "target.py"), UART_PORT, SERVER_PORT, body)
