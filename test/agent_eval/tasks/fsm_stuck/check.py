#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Check: build the target of the workspace and run the engine on several lengths and seeds.

import os
import time

from test.agent_eval.common import CheckResult, run_sim_check

TIER        = "v1"            # Fault visible in the source.
AGENT_PORTS = range(21200, 21250) # Ports given to the agent (UART, litex_server, ...).
UART_PORT   = 21250
SERVER_PORT = 21251
RUNS        = [(16, 0x100), (1000, 0x100), (300, 0xfffffff0), (65535, 0x12345678), (1, 7)]

def _run(regs, length, seed, timeout=20):
    regs.engine_length.write(length)
    regs.engine_seed.write(seed)
    regs.engine_control.write(1)
    start = time.time()
    while not (regs.engine_status.read() & 0x2):
        if (time.time() - start) > timeout:
            return None
        time.sleep(0.01)
    return regs.engine_result.read()

def check(workdir):
    result = CheckResult("fsm_stuck")

    def body(session):
        regs  = session.bus.regs
        names = [n for n in regs.d.keys() if n.startswith("engine_")]
        result.add("register_map", names == ["engine_control", "engine_length", "engine_seed",
            "engine_status", "engine_result"], names)
        for length, seed in RUNS:
            expected = sum(seed + i for i in range(length)) & 0xffffffff
            r = _run(regs, length, seed)
            result.add(f"run_{length}", r == expected,
                f"result {'timeout' if r is None else hex(r)}, expected {expected:#x}")
            if r is None:
                break # The engine is stuck, the next runs would time out too.

    return run_sim_check(result, os.path.join(workdir, "target.py"), UART_PORT, SERVER_PORT, body)
