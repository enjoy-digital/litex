#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Check: run the reference SoC (the task's target.py and soc.json, not the workspace copies) with
# other board information values and verify that the application of the workspace prints them.

import os
import re
import sys
import subprocess

from test.agent_eval.common import CheckResult, run_sim_check

TIER        = "v2"            # Fault only visible at runtime.
AGENT_PORTS = range(21800, 21850) # Ports given to the agent (UART, litex_server, ...).
UART_PORT   = 21850
SERVER_PORT = 21851
SERIAL      = 0x00003e7700b10c42 # Not the values of the prompt.
CAL_GAIN    = 0x0000f5c3
CAL_OFFSET  = 0x0456

def check(workdir):
    result = CheckResult("stale_regs")
    target = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace", "target.py")

    def body(session):
        r = subprocess.run([sys.executable, "app.py", f"--port={SERVER_PORT}"],
            cwd=workdir, capture_output=True, text=True, timeout=120)
        out = r.stdout
        result.add("app_runs", r.returncode == 0, (r.stdout + r.stderr)[-500:])
        def field(pattern):
            m = re.search(pattern, out)
            return None if m is None else m.group(1)
        result.add("id",         field(r"id: 0x(\w+)") == "4c58424f", field(r"id: (.*)"))
        result.add("serial",     field(r"serial: 0x(\w+)") == f"{SERIAL:016x}", field(r"serial: (.*)"))
        result.add("cal_gain",   field(r"cal_gain: 0x(\w+)") == f"{CAL_GAIN:08x}", field(r"cal_gain: (.*)"))
        result.add("cal_offset", field(r"cal_offset: (\d+)") == str(CAL_OFFSET), field(r"cal_offset: (.*)"))
        result.add("scratch",    field(r"scratch: (\w+)") == "OK", field(r"scratch: (.*)"))

    return run_sim_check(result, target, UART_PORT, SERVER_PORT, body,
        args=[f"--serial={SERIAL:#x}", f"--cal-gain={CAL_GAIN:#x}", f"--cal-offset={CAL_OFFSET:#x}"])
