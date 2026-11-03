#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Check: compare answer.json with the truth of the reports (cell names compared without the pin).

import os
import json

from test.agent_eval.common import CheckResult

TIER        = "v1"            # Fault visible in the source.
AGENT_PORTS = range(21400, 21450) # Ports given to the agent (none used, MCP configuration).

TRUTH = {
    "timing_met"     : False,
    "wns_ns"         : -0.734,
    "tns_ns"         : -2.871,
    "failing_clocks" : {"eth_rx_clk", "eth_tx_clk"},
    "worst_paths"    : [
        ("eth_rx_clk", -0.734, "ethmac_rx_converter_converter_mux_reg[1]",     "ethmac_crc32_checker_crc_reg_reg[23]"),
        ("eth_rx_clk", -0.698, "ethmac_rx_converter_converter_mux_reg[0]",     "ethmac_crc32_checker_crc_reg_reg[19]"),
        ("eth_rx_clk", -0.512, "ethmac_crc32_checker_syncfifo_level_reg[2]", "ethmac_crc32_checker_crc_reg_reg[7]"),
    ],
}

def _cell(name):
    # "a_reg[1]/C" -> "a_reg[1]".
    return str(name).strip().rsplit("/", 1)[0] if "/" in str(name) else str(name).strip()

def _close(a, b, tolerance=0.0015):
    try:
        return abs(float(a) - b) <= tolerance
    except (TypeError, ValueError):
        return False

def check(workdir):
    result = CheckResult("timing_triage")
    try:
        with open(os.path.join(workdir, "answer.json")) as f:
            answer = json.load(f)
    except (OSError, ValueError) as e:
        result.add("answer_json", False, f"{type(e).__name__}: {e}")
        return result
    result.add("answer_json", isinstance(answer, dict), type(answer).__name__)
    if not isinstance(answer, dict):
        return result

    result.add("timing_met", answer.get("timing_met") is TRUTH["timing_met"], answer.get("timing_met"))
    result.add("wns_ns", _close(answer.get("wns_ns"), TRUTH["wns_ns"]), answer.get("wns_ns"))
    result.add("tns_ns", _close(answer.get("tns_ns"), TRUTH["tns_ns"]), answer.get("tns_ns"))
    clocks = answer.get("failing_clocks")
    result.add("failing_clocks", isinstance(clocks, list) and set(clocks) == TRUTH["failing_clocks"], clocks)

    paths = answer.get("worst_paths")
    paths = paths if isinstance(paths, list) else []
    for i, (clock, slack, source, destination) in enumerate(TRUTH["worst_paths"]):
        p  = paths[i] if i < len(paths) and isinstance(paths[i], dict) else {}
        ok = (p.get("clock") == clock and _close(p.get("slack_ns"), slack) and
            _cell(p.get("source")) == source and _cell(p.get("destination")) == destination)
        result.add(f"worst_path_{i}", ok, p)
    return result
