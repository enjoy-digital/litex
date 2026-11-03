#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# LiteX SoC on the ECPIX-5 (litex_boards lambdaconcept_ecpix5 target) with the ACME scaler IP
# (vendor netlist, ip/acme_scaler.v) on the Wishbone bus at 0x90000000. The CPU console is on a
# crossover UART and the SoC's bus is reached through a UARTBone bridge on the FTDI UART:
#   ./target.py --uart-name=crossover --with-uartbone --build --load --busdev=<bus:dev>
#   litex_server --uart --uart-port=<ftdi uart> --uart-baudrate=115200 --bind-port=22001
# Loading is to SRAM only (openFPGALoader -c ft2232 --busdev-num <bus:dev>), never to flash.

import os
import subprocess

from migen import *

from litex.gen import *

from litex_boards.platforms import lambdaconcept_ecpix5
from litex_boards.targets.lambdaconcept_ecpix5 import BaseSoC

from litex.soc.interconnect import wishbone
from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.builder import Builder

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

# SoC ----------------------------------------------------------------------------------------------

class ScalerSoC(BaseSoC):
    def __init__(self, **kwargs):
        BaseSoC.__init__(self, **kwargs)
        self.scaler = ACMEScaler(self.platform)
        self.bus.add_slave("scaler", self.scaler.bus, SoCRegion(origin=0x90000000, size=0x100, cached=False))

# Main ---------------------------------------------------------------------------------------------

def main():
    from litex.build.parser import LiteXArgumentParser
    parser = LiteXArgumentParser(platform=lambdaconcept_ecpix5.Platform, description="ACME scaler SoC on ECPIX-5.")
    parser.add_target_argument("--device",       default="85F",            help="ECP5 device (45F or 85F).")
    parser.add_target_argument("--sys-clk-freq", default=75e6, type=float, help="System clock frequency.")
    parser.add_target_argument("--busdev",       default=None,             help="USB bus:dev of the ECPIX-5 FT2232 (for --load).")
    # Console on a crossover UART, UARTBone on the FTDI UART.
    parser.set_defaults(uart_name="crossover", with_uartbone=True)
    args = parser.parse_args()

    soc = ScalerSoC(
        device       = args.device,
        sys_clk_freq = args.sys_clk_freq,
        toolchain    = args.toolchain,
        **parser.soc_argdict
    )
    builder = Builder(soc, **parser.builder_argdict)
    if args.build:
        builder.build(**parser.toolchain_argdict)
    else:
        builder.build(**parser.toolchain_argdict, run=False)

    # Load to SRAM (never flash), on the FT2232 at --busdev (several FT2232 cables on the host).
    if args.load:
        if args.busdev is None:
            parser.error("--load requires --busdev=<bus:dev> (see lsusb).")
        subprocess.run(["openFPGALoader", "-c", "ft2232", "--busdev-num", args.busdev,
            builder.get_bitstream_filename(mode="sram")], check=True)

if __name__ == "__main__":
    main()
