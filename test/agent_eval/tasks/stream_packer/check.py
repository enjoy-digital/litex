#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Check: run the reference test harness (the task's target.py, not the workspace copy) with the
# packer of the workspace (packer.py), on several back-pressure levels and packet lengths, and
# check the throughput without back-pressure.

import os
import time
import shutil
import tempfile

from test.agent_eval.common import CheckResult, run_sim_check

TIER        = "v2"            # Fault only visible at runtime.
AGENT_PORTS = range(21600, 21650) # Ports given to the agent (UART, litex_server, ...).
UART_PORT   = 21650
SERVER_PORT = 21651

# (packets, length_min, length_mask, backpressure)
RUNS = [
    (500,  1, 63, 0),
    (2000, 1, 63, 8),
    (2000, 4, 7,  12),
    (1000, 1, 3,  15),
    (1000, 8, 31, 4),
]

def _run(regs, packets, length_min, length_mask, backpressure, timeout=120):
    regs.test_packets.write(packets)
    regs.test_length_min.write(length_min)
    regs.test_length_mask.write(length_mask)
    regs.test_backpressure.write(backpressure)
    regs.test_control.write(1)
    start = time.time()
    while not (regs.test_status.read() & 0x2):
        if (time.time() - start) > timeout:
            return None
        time.sleep(0.05)
    return {name: getattr(regs, f"test_{name}").read() for name in
        ["tx_packets", "tx_bytes", "rx_packets", "rx_bytes", "data_errors", "cycles"]}

def check(workdir):
    result = CheckResult("stream_packer")
    if not os.path.exists(os.path.join(workdir, "packer.py")):
        result.error = "packer.py not found."
        return result
    tmp = tempfile.mkdtemp(prefix="litex_agent_eval_stream_packer_")
    shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace", "target.py"), tmp)
    shutil.copy(os.path.join(workdir, "packer.py"), tmp)

    def body(session):
        regs = session.bus.regs
        for packets, length_min, length_mask, backpressure in RUNS:
            name = f"run_{packets}_{length_min}_{length_mask}_bp{backpressure}"
            r    = _run(regs, packets, length_min, length_mask, backpressure)
            if r is None:
                result.add(name, False, "timeout")
                break
            ok = (r["tx_packets"] == packets and r["rx_packets"] == packets and
                r["rx_bytes"] == r["tx_bytes"] and r["data_errors"] == 0)
            if backpressure == 0:
                # Full throughput: one byte per cycle (plus a small latency).
                ok &= r["cycles"] <= r["tx_bytes"] + 16
            result.add(name, ok, r)

    try:
        return run_sim_check(result, os.path.join(tmp, "target.py"), UART_PORT, SERVER_PORT, body)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
