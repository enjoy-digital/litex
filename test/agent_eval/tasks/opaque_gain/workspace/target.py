#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Simulated SoC with the ACME scaler IP (vendor netlist, ip/acme_scaler.v) on the Wishbone bus at
# 0x30000000, reachable through a UARTBone bridge:
#   ./target.py --uart-tcp-port=21500
#   litex_server --uart --uart-port=socket://localhost:21500 --bind-port=21501

import os
import argparse

from migen import *

from litex.gen import *

from litex.build.sim.config import SimConfig

from litex.soc.interconnect import wishbone
from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.builder import Builder

from litex.tools.litex_sim import SimSoC

IP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ip")

# ACME Scaler --------------------------------------------------------------------------------------

class ACMEScaler(LiteXModule):
    """Wishbone wrapper of the ACME scaler IP (see ip/DATASHEET.md): the 8 32-bit registers of
    the IP are mapped at offsets 0x00-0x1c of the region."""
    def __init__(self, platform):
        self.bus = bus = wishbone.Interface(data_width=32, address_width=32, addressing="word")

        # # #

        dat_r = Signal(32)
        self.specials += Instance("acme_scaler",
            i_sys_clk = ClockSignal("sys"),
            i_sys_rst = ResetSignal("sys"),
            i_adr     = bus.adr[:3],
            i_we      = bus.cyc & bus.stb & bus.we & ~bus.ack,
            i_dat_w   = bus.dat_w,
            o_dat_r   = dat_r,
        )
        self.sync += [
            bus.ack.eq(bus.cyc & bus.stb & ~bus.ack),
            bus.dat_r.eq(dat_r),
        ]
        platform.add_source(os.path.join(IP_DIR, "acme_scaler.v"))

# Main ---------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Simulated SoC with the ACME scaler IP.")
    parser.add_argument("--uart-tcp-port", default=21500, type=int, help="UARTBone TCP port.")
    parser.add_argument("--output-dir",    default="build/sim",     help="Build directory.")
    args = parser.parse_args()

    # SoC.
    soc = SimSoC(cpu_type=None, with_uart=False, with_uartbone=True)
    soc.scaler = ACMEScaler(soc.platform)
    soc.bus.add_slave("scaler", soc.scaler.bus, SoCRegion(origin=0x30000000, size=0x100, cached=False))

    # Simulation: UARTBone on a TCP port.
    sim_config = SimConfig()
    sim_config.add_clocker("sys_clk", freq_hz=int(1e6))
    sim_config.add_module("serial2tcp", "serial", args={"port": args.uart_tcp_port})

    # Build/Run.
    builder = Builder(soc, output_dir=args.output_dir, csr_csv=os.path.join(args.output_dir, "csr.csv"))
    builder.build(sim_config=sim_config, interactive=False)

if __name__ == "__main__":
    main()
