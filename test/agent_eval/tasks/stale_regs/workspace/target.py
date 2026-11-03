#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Simulated SoC with a board information peripheral, reachable through a UARTBone bridge. The SoC
# options shared with the hardware targets are in soc.json:
#   ./target.py --uart-tcp-port=21800
#   litex_server --uart --uart-port=socket://localhost:21800 --bind-port=21801

import os
import json
import argparse

from migen import *

from litex.gen import *

from litex.build.sim.config import SimConfig

from litex.soc.interconnect.csr import *
from litex.soc.integration.builder import Builder

from litex.tools.litex_sim import SimSoC

# Board Info ---------------------------------------------------------------------------------------

class BoardInfo(LiteXModule):
    """Board information: identifier, serial number, ADC calibration and a scratch register."""
    def __init__(self, serial, cal_gain, cal_offset):
        self.id         = CSRStatus(32, reset=0x4c58424f, description="Identifier (\"LXBO\").")
        self.serial     = CSRStatus(64, reset=serial,     description="Board serial number.")
        self.cal_gain   = CSRStatus(32, reset=cal_gain,   description="ADC calibration gain (Q16.16).")
        self.cal_offset = CSRStatus(16, reset=cal_offset, description="ADC calibration offset.")
        self.scratch    = CSRStorage(32, reset=0x12345678, description="Scratch register.")

# Main ---------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Simulated SoC with a board information peripheral.")
    parser.add_argument("--uart-tcp-port", default=21800, type=int, help="UARTBone TCP port.")
    parser.add_argument("--output-dir",    default="build/sim",     help="Build directory.")
    parser.add_argument("--serial",        default=0x0000a51c00002f17, type=lambda s: int(s, 0), help="Board serial number.")
    parser.add_argument("--cal-gain",      default=0x00010a3d, type=lambda s: int(s, 0), help="Calibration gain (Q16.16).")
    parser.add_argument("--cal-offset",    default=0x0123,     type=lambda s: int(s, 0), help="Calibration offset.")
    args = parser.parse_args()

    # SoC (options shared with the hardware targets).
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "soc.json")) as f:
        soc_options = json.load(f)
    soc = SimSoC(cpu_type=None, with_uart=False, with_uartbone=True, **soc_options)
    soc.info = BoardInfo(serial=args.serial, cal_gain=args.cal_gain, cal_offset=args.cal_offset)

    # Simulation: UARTBone on a TCP port.
    sim_config = SimConfig()
    sim_config.add_clocker("sys_clk", freq_hz=int(1e6))
    sim_config.add_module("serial2tcp", "serial", args={"port": args.uart_tcp_port})

    # Build/Run.
    builder = Builder(soc, output_dir=args.output_dir, csr_csv=os.path.join(args.output_dir, "csr.csv"))
    builder.build(sim_config=sim_config, interactive=False)

if __name__ == "__main__":
    main()
