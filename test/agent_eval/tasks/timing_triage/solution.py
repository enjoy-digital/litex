#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Reference solution: the answer, from the Design Timing Summary, the Intra Clock Table and the
# Max Delay Paths of vivado_build/gateware/top_timing.rpt.

import os
import json

ANSWER = {
    "timing_met"     : False,
    "wns_ns"         : -0.734,
    "tns_ns"         : -2.871,
    "failing_clocks" : ["eth_rx_clk", "eth_tx_clk"],
    "worst_paths"    : [
        {"clock": "eth_rx_clk", "slack_ns": -0.734,
         "source": "ethmac_rx_converter_converter_mux_reg[1]/C", "destination": "ethmac_crc32_checker_crc_reg_reg[23]/D"},
        {"clock": "eth_rx_clk", "slack_ns": -0.698,
         "source": "ethmac_rx_converter_converter_mux_reg[0]/C", "destination": "ethmac_crc32_checker_crc_reg_reg[19]/D"},
        {"clock": "eth_rx_clk", "slack_ns": -0.512,
         "source": "ethmac_crc32_checker_syncfifo_level_reg[2]/C", "destination": "ethmac_crc32_checker_crc_reg_reg[7]/D"},
    ],
}

def solve(workdir):
    with open(os.path.join(workdir, "answer.json"), "w") as f:
        json.dump(ANSWER, f, indent=2)
