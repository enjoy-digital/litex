#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import argparse

from migen import *

from litex.boards.platforms import arty
from litex.build.xilinx.vivado import vivado_build_args, vivado_build_argdict

from litex.soc.cores.clock import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *
from litex.soc.cores.led import LedChaser

from litedram.modules import MT41K128M16
from litedram.phy import s7ddrphy

from liteeth.phy.mii import LiteEthPHYMII

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq, toolchain):
        self.rst = Signal()
        self.clock_domains.cd_sys       = ClockDomain()
        self.clock_domains.cd_sys4x     = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x_dqs = ClockDomain(reset_less=True)
        self.clock_domains.cd_idelay    = ClockDomain()
        self.clock_domains.cd_eth       = ClockDomain()

        # # #

        if toolchain == "vivado":
            self.submodules.pll = pll = S7PLL(speedgrade=-1)
            self.comb += pll.reset.eq(~platform.request("cpu_reset") | self.rst)
            pll.register_clkin(platform.request("clk100"), 100e6)
            pll.create_clkout(self.cd_sys,       sys_clk_freq)
            pll.create_clkout(self.cd_sys4x,     4*sys_clk_freq)
            pll.create_clkout(self.cd_sys4x_dqs, 4*sys_clk_freq, phase=90)
            pll.create_clkout(self.cd_idelay,    200e6)
            pll.create_clkout(self.cd_eth,       25e6)

            self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_idelay)

            self.comb += platform.request("eth_ref_clk").eq(self.cd_eth.clk)
        elif toolchain == "symbiflow": # FIXME
            clk100_ibuf = Signal()
            clk100_buf  = Signal()
            self.specials += Instance("IBUF", i_I=platform.request("clk100"), o_O=clk100_ibuf)
            self.specials += Instance("BUFG", i_I=clk100_ibuf, o_O=clk100_buf)

            self.submodules.pll = pll = S7PLL(speedgrade=-1)
            self.comb += pll.reset.eq(~platform.request("cpu_reset") | self.rst)
            pll.register_clkin(clk100_buf, 100e6)
            pll.create_clkout(self.cd_sys, sys_clk_freq)

            platform.add_period_constraint(clk100_buf, 1e9/100e6)
            platform.add_period_constraint(self.cd_sys.clk, 1e9/sys_clk_freq)
            platform.add_false_path_constraints(clk100_buf, self.cd_sys.clk)

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    def __init__(self, toolchain="vivado", sys_clk_freq=int(100e6), with_ethernet=False, with_etherbone=False, **kwargs):
        platform = arty.Platform(toolchain=toolchain)

        # SoCCore ----------------------------------------------------------------------------------
        if toolchain == "symbiflow":
            sys_clk_freq=int(60e6)

        SoCCore.__init__(self, platform, sys_clk_freq,
            ident          = "LiteX SoC on Arty A7",
            ident_version  = True,
            **kwargs)

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = _CRG(platform, sys_clk_freq, toolchain)

        # DDR3 SDRAM -------------------------------------------------------------------------------
        if not self.integrated_main_ram_size and toolchain != "symbiflow": # FIXME
            self.submodules.ddrphy = s7ddrphy.A7DDRPHY(platform.request("ddram"),
                memtype        = "DDR3",
                nphases        = 4,
                sys_clk_freq   = sys_clk_freq)
            self.add_csr("ddrphy")
            self.add_sdram("sdram",
                phy                     = self.ddrphy,
                module                  = MT41K128M16(sys_clk_freq, "1:4"),
                origin                  = self.mem_map["main_ram"],
                size                    = kwargs.get("max_sdram_size", 0x40000000),
                l2_cache_size           = kwargs.get("l2_size", 8192),
                l2_cache_min_data_width = kwargs.get("min_l2_data_width", 128),
                l2_cache_reverse        = True
            )

        # Ethernet / Etherbone ---------------------------------------------------------------------
        if with_ethernet or with_etherbone:
            self.submodules.ethphy = LiteEthPHYMII(
                clock_pads = self.platform.request("eth_clocks"),
                pads       = self.platform.request("eth"))
            self.add_csr("ethphy")
            if with_ethernet:
                self.add_ethernet(phy=self.ethphy)
            if with_etherbone:
                self.add_etherbone(phy=self.ethphy)

        # Leds -------------------------------------------------------------------------------------
        self.submodules.leds = LedChaser(
            pads         = platform.request_all("user_led"),
            sys_clk_freq = sys_clk_freq)
        self.add_csr("leds")

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on Arty A7")
    parser.add_argument("--build", action="store_true",     help="Build bitstream")
    parser.add_argument("--load",  action="store_true",     help="Load bitstream")
    parser.add_argument("--toolchain", default="vivado",    help="FPGA toolchain: vivado (default) or symbiflow")
    parser.add_argument("--sys-clk-freq",    default=100e6, help="System clock frequency (default: 100MHz)")
    parser.add_argument("--with-ethernet",   action="store_true", help="Enable Ethernet support")
    parser.add_argument("--with-etherbone",  action="store_true", help="Enable Etherbone support")
    parser.add_argument("--with-spi-sdcard", action="store_true", help="Enable SPI-mode SDCard support")
    parser.add_argument("--with-sdcard",     action="store_true", help="Enable SDCard support")
    builder_args(parser)
    soc_sdram_args(parser)
    vivado_build_args(parser)
    args = parser.parse_args()

    assert not (args.with_ethernet and args.with_etherbone)
    soc = BaseSoC(
	    toolchain      = args.toolchain,
        sys_clk_freq   = int(float(args.sys_clk_freq)),
        with_ethernet  = args.with_ethernet,
        with_etherbone = args.with_etherbone,
        **soc_sdram_argdict(args)
    )
    assert not (args.with_spi_sdcard and args.with_sdcard)
    soc.platform.add_extension(arty._sdcard_pmod_io)
    if args.with_spi_sdcard:
        soc.add_spi_sdcard()
    if args.with_sdcard:
        soc.add_sdcard()
    builder = Builder(soc, **builder_argdict(args))
    builder_kwargs = vivado_build_argdict(args) if args.toolchain == "vivado" else {}
    builder.build(**builder_kwargs, run=args.build)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(os.path.join(builder.gateware_dir, soc.build_name + ".bit"))

if __name__ == "__main__":
    main()
