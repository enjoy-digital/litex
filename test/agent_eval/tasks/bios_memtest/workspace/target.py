#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Simulated SoC (VexRiscv CPU, BIOS) with a main RAM, its console on a crossover UART and a
# UARTBone bridge:
#   ./target.py --uart-tcp-port=21300
#   litex_server --uart --uart-port=socket://localhost:21300 --bind-port=21301
#   litex_term crossover --csr-csv=build/sim/csr.csv --port=21301

import os
import argparse

from migen import *

from litex.gen import *

from litex.build.sim.config import SimConfig

from litex.soc.interconnect import wishbone
from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.builder import Builder

from litex.tools.litex_sim import SimSoC

# Main RAM -----------------------------------------------------------------------------------------

class MainRAM(LiteXModule):
    """Main RAM built from 32-bit words of on-chip memory."""
    def __init__(self, size):
        self.size = size
        self.bus  = wishbone.Interface(data_width=32, address_width=32, addressing="word")

        # # #

        self.ram = wishbone.SRAM(size//4, bus=self.bus)

# Main ---------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Simulated SoC with a main RAM.")
    parser.add_argument("--uart-tcp-port", default=21300, type=int, help="UARTBone TCP port.")
    parser.add_argument("--output-dir",    default="build/sim",     help="Build directory.")
    parser.add_argument("--main-ram-size", default=0x10000, type=lambda s: int(s, 0), help="Main RAM size (bytes).")
    args = parser.parse_args()

    # SoC.
    soc = SimSoC(cpu_type="vexriscv", integrated_rom_size=0x20000, uart_name="crossover", with_uartbone=True)
    soc.main_ram = MainRAM(size=args.main_ram_size)
    soc.bus.add_slave("main_ram", soc.main_ram.bus, SoCRegion(origin=soc.mem_map["main_ram"], size=args.main_ram_size))

    # Simulation: UARTBone on a TCP port.
    sim_config = SimConfig()
    sim_config.add_clocker("sys_clk", freq_hz=int(1e6))
    sim_config.add_module("serial2tcp", "serial", args={"port": args.uart_tcp_port})

    # Build/Run.
    builder = Builder(soc, output_dir=args.output_dir, csr_csv=os.path.join(args.output_dir, "csr.csv"))
    builder.build(sim_config=sim_config, interactive=False)

if __name__ == "__main__":
    main()
