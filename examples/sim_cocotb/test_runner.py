#
# This file is part of the LiteX cocotb+Verilator simulation POC.
# See ../../../issues/2380 (enjoy-digital/litex) for background.
#
# Copyright (c) 2026 Vishnu Sentha <vishnusentha@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause
"""
Build ``dut.v`` (via ``dut.py``) and run ``test_dut.py`` under Verilator +
cocotb, using the modern ``cocotb-tools`` Python runner API -- no
hand-written Makefile needed.

    python3 test_runner.py
    # or
    pytest test_runner.py

Requires Verilator >= 5.0 on PATH (see README.md -- it is NOT bundled with
this example; install it separately). Everything else (migen, litex,
cocotb, cocotb-tools) is listed in requirements.txt.
"""
import os
from pathlib import Path

from cocotb_tools.runner import get_runner

import dut as dut_module  # dut.py: elaborates the design, writes dut.v.


def test_dut_runner():
    sim = os.getenv("SIM", "verilator")
    proj_path = Path(__file__).resolve().parent

    # Regenerate dut.v from the Migen/LiteX source on every run, so the
    # Verilog handed to Verilator can never silently drift from dut.py.
    v_file = proj_path / "dut.v"
    dut_module.generate(v_file=str(v_file), top_name="dut")

    runner = get_runner(sim)
    runner.build(
        sources=[v_file],
        hdl_toplevel="dut",
        always=True,
        waves=True,
        # cocotb drives every signal directly (no CPU/bus master), so no
        # timing/synthesis constraints or extra IP are needed here.
        build_args=["--trace", "-Wno-fatal"],
    )
    runner.test(
        hdl_toplevel="dut",
        test_module="test_dut",
        waves=True,
    )


if __name__ == "__main__":
    test_dut_runner()
