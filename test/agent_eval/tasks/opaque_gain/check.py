#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Check: run the reference SoC (the task's target.py and IP netlist, not the workspace copies),
# configure the IP with driver.configure() of the workspace for several gains/offsets, then drive
# the IP registers directly (DIN/STATUS/DOUT) and compare the results with the specification. The
# results are computed by the IP: a driver computing them in software does not pass.

import os
import importlib.util

from test.agent_eval.common import CheckResult, run_sim_check

TIER        = "v2"            # Fault only visible at runtime.
AGENT_PORTS = range(21500, 21550) # Ports given to the agent (UART, litex_server, ...).
UART_PORT   = 21550
SERVER_PORT = 21551

BASE    = 0x30000000
DIN     = BASE + 0x10
DOUT    = BASE + 0x14
STATUS  = BASE + 0x1c
CONFIGS = [(1.5, 100), (0.75, 0), (3.0, 1000), (2.25, 7)]
SAMPLES = [0, 1, 999, 2730, 4000, 9000, 21000, 30000, 47000, 65535]

def _load_driver(workdir):
    spec   = importlib.util.spec_from_file_location("agent_eval_opaque_gain_driver", os.path.join(workdir, "driver.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def check(workdir):
    result = CheckResult("opaque_gain")
    target = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace", "target.py")
    try:
        driver = _load_driver(workdir)
    except Exception as e:
        result.add("driver_import", False, f"{type(e).__name__}: {e}")
        return result

    def body(session):
        bus = session.bus
        for gain, offset in CONFIGS:
            try:
                driver.configure(bus, gain, offset)
            except Exception as e:
                result.add(f"configure_{gain}_{offset}", False, f"{type(e).__name__}: {e}")
                continue
            errors = []
            for x in SAMPLES:
                bus.write(DIN, x)
                for _ in range(10):
                    if bus.read(STATUS) & 0x1:
                        break
                y        = bus.read(DOUT)
                expected = min(int(x*gain) + offset, 0xffff)
                if abs(y - expected) > 1:
                    errors.append(f"x={x} y={y} expected={expected}")
            result.add(f"gain_{gain}_offset_{offset}", not errors, errors[:4])

    return run_sim_check(result, target, UART_PORT, SERVER_PORT, body)
