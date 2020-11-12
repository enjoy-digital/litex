#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2014-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2014-2015 Yann Sionneau <ys@m-labs.hk>
# SPDX-License-Identifier: BSD-2-Clause

import os
import argparse

from migen import *

from litex.boards.platforms import kc705

from litex.soc.cores.clock import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *
from litex.soc.cores.led import LedChaser

from litedram.modules import MT8JTF12864
from litedram.phy import s7ddrphy

from liteeth.phy import LiteEthPHY

from litepcie.phy.s7pciephy import S7PCIEPHY
from litepcie.software import generate_litepcie_software

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.rst = Signal()
        self.clock_domains.cd_sys    = ClockDomain()
        self.clock_domains.cd_sys4x  = ClockDomain(reset_less=True)
        self.clock_domains.cd_idelay = ClockDomain()

        # # #

        self.submodules.pll = pll = S7MMCM(speedgrade=-2)
        self.comb += pll.reset.eq(platform.request("cpu_reset") | self.rst)
        pll.register_clkin(platform.request("clk200"), 200e6)
        pll.create_clkout(self.cd_sys,    sys_clk_freq)
        pll.create_clkout(self.cd_sys4x,  4*sys_clk_freq)
        pll.create_clkout(self.cd_idelay, 200e6)

        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_idelay)

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    def __init__(self, sys_clk_freq=int(125e6), with_ethernet=False, with_pcie=False, with_sata=False, **kwargs):
        platform = kc705.Platform()

        # SoCCore ----------------------------------------------------------------------------------
        SoCCore.__init__(self, platform, sys_clk_freq,
            ident          = "LiteX SoC on KC705",
            ident_version  = True,
            **kwargs)

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = _CRG(platform, sys_clk_freq)

        # DDR3 SDRAM -------------------------------------------------------------------------------
        if not self.integrated_main_ram_size:
            self.submodules.ddrphy = s7ddrphy.K7DDRPHY(platform.request("ddram"),
                memtype      = "DDR3",
                nphases      = 4,
                sys_clk_freq = sys_clk_freq)
            self.add_csr("ddrphy")
            self.add_sdram("sdram",
                phy                     = self.ddrphy,
                module                  = MT8JTF12864(sys_clk_freq, "1:4"),
                origin                  = self.mem_map["main_ram"],
                size                    = kwargs.get("max_sdram_size", 0x40000000),
                l2_cache_size           = kwargs.get("l2_size", 8192),
                l2_cache_min_data_width = kwargs.get("min_l2_data_width", 128),
                l2_cache_reverse        = True
            )

        # Ethernet ---------------------------------------------------------------------------------
        if with_ethernet:
            self.submodules.ethphy = LiteEthPHY(
                clock_pads = self.platform.request("eth_clocks"),
                pads       = self.platform.request("eth"),
                clk_freq   = self.clk_freq)
            self.add_csr("ethphy")
            self.add_ethernet(phy=self.ethphy)

        # PCIe -------------------------------------------------------------------------------------
        if with_pcie:
            self.submodules.pcie_phy = S7PCIEPHY(platform, platform.request("pcie_x4"),
                data_width = 128,
                bar0_size  = 0x20000)
            self.add_csr("pcie_phy")
            self.add_pcie(phy=self.pcie_phy, ndmas=1)

        # SATA -------------------------------------------------------------------------------------
        if with_sata:
            from litex.build.generic_platform import Subsignal, Pins
            from litesata.phy import LiteSATAPHY

            # IOs
            _sata_io = [
                # SFP 2 SATA Adapter / https://shop.trenz-electronic.de/en/TE0424-01-SFP-2-SATA-Adapter
                ("sfp2sata", 0,
                    Subsignal("tx_p", Pins("H2")),
                    Subsignal("tx_n", Pins("H1")),
                    Subsignal("rx_p", Pins("G4")),
                    Subsignal("rx_n", Pins("G3")),
                ),
            ]
            platform.add_extension(_sata_io)

            # RefClk, Generate 150MHz from PLL.
            self.clock_domains.cd_sata_refclk = ClockDomain()
            self.crg.pll.create_clkout(self.cd_sata_refclk, 150e6)
            sata_refclk = ClockSignal("sata_refclk")
            platform.add_platform_command("set_property SEVERITY {{Warning}} [get_drc_checks REQP-52]")

            # PHY
            self.submodules.sata_phy = LiteSATAPHY(platform.device,
                refclk     = sata_refclk,
                pads       = platform.request("sfp2sata"),
                gen        = "gen2",
                clk_freq   = sys_clk_freq,
                data_width = 16)
            self.add_csr("sata_phy")

            # Core
            self.add_sata(phy=self.sata_phy, mode="read+write")

        # Leds -------------------------------------------------------------------------------------
        self.submodules.leds = LedChaser(
            pads         = platform.request_all("user_led"),
            sys_clk_freq = sys_clk_freq)
        self.add_csr("leds")

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on KC705")
    parser.add_argument("--build",         action="store_true", help="Build bitstream")
    parser.add_argument("--load",          action="store_true", help="Load bitstream")
    parser.add_argument("--sys-clk-freq",  default=125e6,       help="System clock frequency (default: 125MHz)")
    parser.add_argument("--with-ethernet", action="store_true", help="Enable Ethernet support")
    parser.add_argument("--with-pcie",     action="store_true", help="Enable PCIe support")
    parser.add_argument("--driver",        action="store_true", help="Generate PCIe driver")
    parser.add_argument("--with-sata",     action="store_true", help="Enable SATA support (over SFP2SATA)")
    builder_args(parser)
    soc_sdram_args(parser)
    args = parser.parse_args()

    soc = BaseSoC(
        sys_clk_freq  = int(float(args.sys_clk_freq)),
        with_ethernet = args.with_ethernet,
        with_pcie     = args.with_pcie,
        with_sata     = args.with_sata,
        **soc_sdram_argdict(args)
    )
    builder = Builder(soc, **builder_argdict(args))
    builder.build(run=args.build)

    if args.driver:
        generate_litepcie_software(soc, os.path.join(builder.output_dir, "driver"))

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(os.path.join(builder.gateware_dir, soc.build_name + ".bit"))

if __name__ == "__main__":
    main()
