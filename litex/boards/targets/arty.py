#!/usr/bin/env python3

# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import argparse

from migen import *

from litex.boards.platforms import arty
from litex.build.xilinx.vivado import vivado_build_args, vivado_build_argdict

from litex.soc.cores.clock import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *
from litex.soc.cores.spi_flash import *
from litedram.modules import MT41K128M16
from litedram.phy import s7ddrphy

from liteeth.phy.mii import LiteEthPHYMII

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_sys       = ClockDomain()
        self.clock_domains.cd_sys2x     = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x     = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x_dqs = ClockDomain(reset_less=True)
        self.clock_domains.cd_clk200    = ClockDomain()
        self.clock_domains.cd_eth       = ClockDomain()

        # # #

        self.submodules.pll = pll = S7PLL(speedgrade=-1)
        self.comb += pll.reset.eq(~platform.request("cpu_reset"))
        pll.register_clkin(platform.request("clk100"), 100e6)
        pll.create_clkout(self.cd_sys,       sys_clk_freq)
        pll.create_clkout(self.cd_sys2x,     2*sys_clk_freq)
        pll.create_clkout(self.cd_sys4x,     4*sys_clk_freq)
        pll.create_clkout(self.cd_sys4x_dqs, 4*sys_clk_freq, phase=90)
        pll.create_clkout(self.cd_clk200,    200e6)
        pll.create_clkout(self.cd_eth,       25e6)

        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_clk200)

        self.comb += platform.request("eth_ref_clk").eq(self.cd_eth.clk)

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    mem_map = {
        "spi_flash4x0": 0x50000000,
    }
    mem_map.update(SoCSDRAM.mem_map)
    
    def __init__(self, sys_clk_freq=int(100e6), with_ethernet=False, with_etherbone=False, **kwargs):
        platform = arty.Platform()

        # SoCCore ----------------------------------------------------------------------------------
        SoCCore.__init__(self, platform, clk_freq=sys_clk_freq, **kwargs)

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = _CRG(platform, sys_clk_freq)

        # DDR3 SDRAM -------------------------------------------------------------------------------
        if not self.integrated_main_ram_size:
            self.submodules.ddrphy = s7ddrphy.A7DDRPHY(platform.request("ddram"),
                memtype        = "DDR3",
                nphases        = 4,
                sys_clk_freq   = sys_clk_freq,
                interface_type = "MEMORY")
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

        # Ethernet ---------------------------------------------------------------------------------
        if with_ethernet:
            self.submodules.ethphy = LiteEthPHYMII(
                clock_pads = self.platform.request("eth_clocks"),
                pads       = self.platform.request("eth"))
            self.add_csr("ethphy")
            self.add_ethernet(phy=self.ethphy)

        # Etherbone --------------------------------------------------------------------------------
        if with_etherbone:
            self.submodules.ethphy = LiteEthPHYMII(
                clock_pads = self.platform.request("eth_clocks"),
                pads       = self.platform.request("eth"))
            self.add_csr("ethphy")
            self.add_etherbone(phy=self.ethphy)

        # spi_flash
        pads = self.platform.request("spiflash4x", 0)
        self.submodules.spi_flash4x0 = SpiFlash(pads, dummy=10, div=2, with_bitbang=True, endianness="little", with_quad=True)
        self.add_memory_region("spi_flash4x0", self.mem_map["spi_flash4x0"], 0x1000000)
        self.add_wb_slave(self.mem_regions["spi_flash4x0"].origin, self.spi_flash4x0.bus, 0x1000000)        
        self.add_csr("spi_flash4x0")
# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on Arty")
    builder_args(parser)
    soc_sdram_args(parser)
    vivado_build_args(parser)
    parser.add_argument("--with-ethernet", action="store_true", help="enable Ethernet support")
    parser.add_argument("--with-etherbone", action="store_true", help="enable Etherbone support")
    args = parser.parse_args()

    assert not (args.with_ethernet and args.with_etherbone)
    soc = BaseSoC(with_ethernet=args.with_ethernet, with_etherbone=args.with_etherbone,
        **soc_sdram_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build(**vivado_build_argdict(args))


if __name__ == "__main__":
    main()
