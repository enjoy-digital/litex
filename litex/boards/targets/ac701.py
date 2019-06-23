# This file is Copyright (c) 2019 Vamsi K Vytla <vamsi.vytla@gmail.com>
# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

#!/usr/bin/env python3

import argparse

from migen import *

from litex.boards.platforms import ac701

from litex.soc.cores.clock import *
from litex.soc.integration.soc_core import mem_decoder
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *

from litedram.modules import MT8JTF12864
from litedram.phy import s7ddrphy

from liteeth.phy.a7_gtp import QPLLSettings, QPLL
from liteeth.phy.a7_1000basex import A7_1000BASEX
from liteeth.phy.s7rgmii import LiteEthPHYRGMII
from liteeth.core.mac import LiteEthMAC

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys4x = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x_dqs = ClockDomain(reset_less=True)
        self.clock_domains.cd_clk200 = ClockDomain()

        # # #

        self.cd_sys.clk.attr.add("keep")
        self.cd_sys4x.clk.attr.add("keep")
        self.cd_sys4x_dqs.clk.attr.add("keep")

        self.submodules.pll = pll = S7PLL(speedgrade=-1)
        self.comb += pll.reset.eq(~platform.request("cpu_reset"))
        pll.register_clkin(platform.request("clk200"), 200e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
        pll.create_clkout(self.cd_sys4x, 4*sys_clk_freq)
        pll.create_clkout(self.cd_sys4x_dqs, 4*sys_clk_freq, phase=90)
        pll.create_clkout(self.cd_clk200, 200e6)

        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_clk200)

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCSDRAM):
    def __init__(self, sys_clk_freq=int(100e6), **kwargs):
        platform = ac701.Platform()
        SoCSDRAM.__init__(self, platform, clk_freq=sys_clk_freq,
                         integrated_rom_size=0x8000,
                         integrated_sram_size=0x8000,
                          **kwargs)

        self.submodules.crg = _CRG(platform, sys_clk_freq)

        # sdram
        self.submodules.ddrphy = s7ddrphy.A7DDRPHY(platform.request("ddram"), sys_clk_freq=sys_clk_freq)
        self.add_csr("ddrphy")
        sdram_module = MT8JTF12864(sys_clk_freq, "1:4")
        self.register_sdram(self.ddrphy,
                            sdram_module.geom_settings,
                            sdram_module.timing_settings)

# EthernetSoC --------------------------------------------------------------------------------------

class EthernetSoC(BaseSoC):
    mem_map = {
        "ethmac": 0x30000000,  # (shadow @0xb0000000)
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, phy="rgmii", **kwargs):
        assert phy in ["rgmii", "1000basex"]
        BaseSoC.__init__(self, **kwargs)

        if phy == "rgmii":
            self.submodules.ethphy = LiteEthPHYRGMII(self.platform.request("eth_clocks"),
                                                     self.platform.request("eth"))
            self.add_csr("ethphy")
            self.ethphy.crg.cd_eth_rx.clk.attr.add("keep")
            self.ethphy.crg.cd_eth_tx.clk.attr.add("keep")
            self.platform.add_period_constraint(self.ethphy.crg.cd_eth_rx.clk, 1e9/125e6)
            self.platform.add_period_constraint(self.ethphy.crg.cd_eth_tx.clk, 1e9/125e6)
            self.platform.add_false_path_constraints(
                self.crg.cd_sys.clk,
                self.ethphy.crg.cd_eth_rx.clk,
                self.ethphy.crg.cd_eth_tx.clk)

        if phy == "1000basex":
            self.comb += self.platform.request("sfp_mgt_clk_sel0", 0).eq(0)
            self.comb += self.platform.request("sfp_mgt_clk_sel1", 0).eq(0)
            self.comb += self.platform.request("sfp_tx_disable_n", 0).eq(0)
            qpll_settings = QPLLSettings(
                refclksel=0b001,
                fbdiv=4,
                fbdiv_45=5,
                refclk_div=1)
            refclk125 = self.platform.request("gtp_refclk")
            refclk125_se = Signal()
            self.specials += \
                Instance("IBUFDS_GTE2",
                    i_CEB=0,
                    i_I=refclk125.p,
                    i_IB=refclk125.n,
                    o_O=refclk125_se)
            qpll = QPLL(refclk125_se, qpll_settings)
            self.submodules += qpll
            self.submodules.ethphy = A7_1000BASEX(qpll.channels[0], self.platform.request("sfp", 0), self.clk_freq)
            self.platform.add_period_constraint(self.ethphy.txoutclk, 1e9/62.5e6)
            self.platform.add_period_constraint(self.ethphy.rxoutclk, 1e9/62.5e6)
            self.platform.add_false_path_constraints(
                self.crg.cd_sys.clk,
                self.ethphy.txoutclk,
                self.ethphy.rxoutclk)

        self.submodules.ethmac = LiteEthMAC(phy=self.ethphy, dw=32,
            interface="wishbone", endianness=self.cpu.endianness)
        self.add_wb_slave(mem_decoder(self.mem_map["ethmac"]), self.ethmac.bus)
        self.add_memory_region("ethmac", self.mem_map["ethmac"] | self.shadow_base, 0x2000)
        self.add_csr("ethmac")
        self.add_interrupt("ethmac")

# Build --------------------------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on AC701")
    builder_args(parser)
    soc_sdram_args(parser)
    parser.add_argument("--with-ethernet", action="store_true",
                        help="enable Ethernet support")
    parser.add_argument("--ethernet-phy", default="rgmii",
                        help="select Ethernet PHY (rgmii or 1000basex)")
    args = parser.parse_args()

    if args.with_ethernet:
        soc = EthernetSoC(args.ethernet_phy, **soc_sdram_argdict(args))
    else:
        soc = BaseSoC(**soc_sdram_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()


if __name__ == "__main__":
    main()
