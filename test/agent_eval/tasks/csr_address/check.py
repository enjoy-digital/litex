#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Check: run the reference SoC with another sensor reading and verify that the monitor of the
# workspace prints it.

import os
import re
import sys
import shutil
import subprocess

from test.agent_eval.common import CheckResult, run_sim_check

AGENT_PORTS = range(21000, 21050) # Ports given to the agent (UART, litex_server, ...).
UART_PORT   = 21050
SERVER_PORT = 21051
SENSOR_RAW  = 0x1b7 # 27.44 C, not the value given in the prompt.

def check(workdir):
    result = CheckResult("csr_address")
    target = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace", "target.py")

    def body(session):
        # The monitor finds the SoC's csr.csv in build/sim (as documented in the prompt).
        os.makedirs(os.path.join(workdir, "build", "sim"), exist_ok=True)
        shutil.copy(session.csr_csv, os.path.join(workdir, "build", "sim", "csr.csv"))
        r = subprocess.run([sys.executable, "monitor.py", f"--port={SERVER_PORT}"],
            cwd=workdir, capture_output=True, text=True, timeout=60)
        result.add("monitor_runs", r.returncode == 0, (r.stdout + r.stderr)[-500:])
        m = re.search(r"temperature:\s*(-?[\d.]+)\s*C", r.stdout)
        expected = SENSOR_RAW/16
        result.add("temperature", m is not None and abs(float(m.group(1)) - expected) < 0.01,
            f"expected {expected:.2f} C, got: {r.stdout.strip()[-200:]}")

    return run_sim_check(result, target, UART_PORT, SERVER_PORT, body,
        args=[f"--sensor-raw={SENSOR_RAW:#x}"])
