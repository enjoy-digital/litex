#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Check: build the target of the workspace with the delivered firmware (the task's copy) and other
# ADC values, and verify the per-channel values printed by the firmware.

import os
import re
import time

from test.agent_eval.common import CheckResult, run_sim_check

TIER        = "v2"            # Fault only visible at runtime.
AGENT_PORTS = range(21700, 21750) # Ports given to the agent (UART, litex_server, ...).
UART_PORT   = 21750
SERVER_PORT = 21751
FIRMWARE    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace", "firmware", "sampler.bin")
ADC_VALUES  = [0x2b4, 0x019, 0x5e6, 0xc03] # Not the values of the prompt.

PASS_RE = re.compile(r"pass \d+: ch0=0x(\w+) ch1=0x(\w+) ch2=0x(\w+) ch3=0x(\w+) channel check: (\w+)")

def check(workdir):
    result = CheckResult("firmware_blob")

    def body(session):
        log   = ""
        start = time.time()
        while len(PASS_RE.findall(log)) < 2 and (time.time() - start) < 300:
            log += session.console_read(timeout=1.0)
        passes = PASS_RE.findall(log)
        result.add("firmware_runs", "sampler v2.3" in log and len(passes) >= 2, log[-300:])
        if passes:
            values = [int(v, 16) for v in passes[-1][:4]]
            result.add("channel_check", passes[-1][4] == "OK", passes[-1])
            result.add("channel_values", values == ADC_VALUES,
                f"{[hex(v) for v in values]}, expected {[hex(v) for v in ADC_VALUES]}")
        names = [n for n in session.bus.regs.d.keys() if n.startswith("adc_")]
        result.add("register_map", names == ["adc_control", "adc_status", "adc_data"], names)

    return run_sim_check(result, os.path.join(workdir, "target.py"), UART_PORT, SERVER_PORT, body,
        args=[f"--firmware={FIRMWARE}", "--adc-values=" + ",".join(hex(v) for v in ADC_VALUES)])
