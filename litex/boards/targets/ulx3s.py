#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2018 David Shah <dave@ds0.me>
# SPDX-License-Identifier: BSD-2-Clause

import os
import argparse
import sys

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import DDROutput

from litex.boards.platforms import ulx3s

from litex.build.lattice.trellis import trellis_args, trellis_argdict

from litex.soc.cores.clock import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *
from litex.soc.cores.led import LedChaser
from litex.soc.cores.spi import SPIMaster
from litex.soc.cores.gpio import GPIOOut

from litedram import modules as litedram_modules
from litedram.phy import GENSDRPHY, HalfRateGENSDRPHY

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq, with_usb_pll=False, sdram_rate="1:1"):
        self.rst = Signal()
        self.clock_domains.cd_sys    = ClockDomain()
        if sdram_rate == "1:2":
            self.clock_domains.cd_sys2x    = ClockDomain()
            self.clock_domains.cd_sys2x_ps = ClockDomain(reset_less=True)
        else:
            self.clock_domains.cd_sys_ps = ClockDomain(reset_less=True)

        # # #

        # Clk / Rst
        clk25 = platform.request("clk25")
        rst   = platform.request("rst")

        # PLL
        self.submodules.pll = pll = ECP5PLL()
        self.comb += pll.reset.eq(rst | self.rst)
        pll.register_clkin(clk25, 25e6)
        pll.create_clkout(self.cd_sys,    sys_clk_freq)
        if sdram_rate == "1:2":
            pll.create_clkout(self.cd_sys2x,    2*sys_clk_freq)
            pll.create_clkout(self.cd_sys2x_ps, 2*sys_clk_freq, phase=180) # Idealy 90° but needs to be increased.
        else:
           pll.create_clkout(self.cd_sys_ps, sys_clk_freq, phase=90)

        # USB PLL
        if with_usb_pll:
            self.submodules.usb_pll = usb_pll = ECP5PLL()
            self.comb += usb_pll.reset.eq(rst | self.rst)
            usb_pll.register_clkin(clk25, 25e6)
            self.clock_domains.cd_usb_12 = ClockDomain()
            self.clock_domains.cd_usb_48 = ClockDomain()
            usb_pll.create_clkout(self.cd_usb_12, 12e6, margin=0)
            usb_pll.create_clkout(self.cd_usb_48, 48e6, margin=0)

        # SDRAM clock
        sdram_clk = ClockSignal("sys2x_ps" if sdram_rate == "1:2" else "sys_ps")
        self.specials += DDROutput(1, 0, platform.request("sdram_clock"), sdram_clk)

        # Prevent ESP32 from resetting FPGA
        self.comb += platform.request("wifi_gpio0").eq(1)

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    def __init__(self, device="LFE5U-45F", revision="2.0", toolchain="trellis",
        sys_clk_freq=int(50e6), sdram_module_cls="MT48LC16M16", sdram_rate="1:1", **kwargs):
        platform = ulx3s.Platform(device=device, revision=revision, toolchain=toolchain)

        # SoCCore ----------------------------------------------------------------------------------
        SoCCore.__init__(self, platform, sys_clk_freq,
            ident          = "LiteX SoC on ULX3S",
            ident_version  = True,
            **kwargs)

        # CRG --------------------------------------------------------------------------------------
        with_usb_pll = kwargs.get("uart_name", None) == "usb_acm"
        self.submodules.crg = _CRG(platform, sys_clk_freq, with_usb_pll, sdram_rate=sdram_rate)

        # SDR SDRAM --------------------------------------------------------------------------------
        if not self.integrated_main_ram_size:
            sdrphy_cls = HalfRateGENSDRPHY if sdram_rate == "1:2" else GENSDRPHY
            self.submodules.sdrphy = sdrphy_cls(platform.request("sdram"))
            self.add_sdram("sdram",
                phy                     = self.sdrphy,
                module                  = getattr(litedram_modules, sdram_module_cls)(sys_clk_freq, sdram_rate),
                origin                  = self.mem_map["main_ram"],
                size                    = kwargs.get("max_sdram_size", 0x40000000),
                l2_cache_size           = kwargs.get("l2_size", 8192),
                l2_cache_min_data_width = kwargs.get("min_l2_data_width", 128),
                l2_cache_reverse        = True
            )

        # Leds -------------------------------------------------------------------------------------
        self.submodules.leds = LedChaser(
            pads         = platform.request_all("user_led"),
            sys_clk_freq = sys_clk_freq)
        self.add_csr("leds")

    def add_oled(self):
        pads = self.platform.request("oled_spi")
        pads.miso = Signal()
        self.submodules.oled_spi = SPIMaster(pads, 8, self.sys_clk_freq, 8e6)
        self.oled_spi.add_clk_divider()
        self.add_csr("oled_spi")

        self.submodules.oled_ctl = GPIOOut(self.platform.request("oled_ctl"))
        self.add_csr("oled_ctl")

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on ULX3S")
    parser.add_argument("--build",           action="store_true",   help="Build bitstream")
    parser.add_argument("--load",            action="store_true",   help="Load bitstream")
    parser.add_argument("--toolchain",       default="trellis",     help="FPGA toolchain: trellis (default) or diamond")
    parser.add_argument("--device",          default="LFE5U-45F",   help="FPGA device: LFE5U-12F, LFE5U-25F, LFE5U-45F (default)  or LFE5U-85F")
    parser.add_argument("--revision",        default="2.0",         help="Board revision: 2.0 (default) or 1.7")
    parser.add_argument("--sys-clk-freq",    default=50e6,          help="System clock frequency  (default: 50MHz)")
    parser.add_argument("--sdram-module",    default="MT48LC16M16", help="SDRAM module: MT48LC16M16 (default), AS4C32M16 or AS4C16M16")
    parser.add_argument("--with-spi-sdcard", action="store_true",   help="Enable SPI-mode SDCard support")
    parser.add_argument("--with-sdcard",     action="store_true",   help="Enable SDCard support")
    parser.add_argument("--with-oled",       action="store_true",   help="Enable SDD1331 OLED support")
    parser.add_argument("--sdram-rate",      default="1:1",         help="SDRAM Rate: 1:1 Full Rate (default), 1:2 Half Rate")
    builder_args(parser)
    soc_sdram_args(parser)
    trellis_args(parser)
    args = parser.parse_args()

    soc = BaseSoC(
        device           = args.device,
        revision         = args.revision,
        toolchain        = args.toolchain,
        sys_clk_freq     = int(float(args.sys_clk_freq)),
        sdram_module_cls = args.sdram_module,
        sdram_rate       = args.sdram_rate,
        **soc_sdram_argdict(args))
    assert not (args.with_spi_sdcard and args.with_sdcard)
    if args.with_spi_sdcard:
        soc.add_spi_sdcard()
    if args.with_sdcard:
        soc.add_sdcard()
    if args.with_oled:
        soc.add_oled()

    builder = Builder(soc, **builder_argdict(args))
    builder_kargs = trellis_argdict(args) if args.toolchain == "trellis" else {}
    builder.build(**builder_kargs, run=args.build)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(os.path.join(builder.gateware_dir, soc.build_name + ".svf"))

if __name__ == "__main__":
    main()
