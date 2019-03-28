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

from liteeth.phy.a7_gtp import *
from liteeth.phy.a7_1000basex import A7_1000BASEX
from liteeth.phy import LiteEthPHY
from liteeth.core import LiteEthUDPIPCore

from liteeth.frontend.etherbone import LiteEthEtherbone


class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys4x = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x_dqs = ClockDomain(reset_less=True)
        self.clock_domains.cd_clk200 = ClockDomain()
        self.clock_domains.cd_clk1x = ClockDomain()
        self.clock_domains.cd_clk2x = ClockDomain()

        self.submodules.pll = pll = S7MMCM(speedgrade=-2)
        self.comb += pll.reset.eq(platform.request("cpu_reset"))
        pll.register_clkin(platform.request("clk200"), 200e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
        pll.create_clkout(self.cd_sys4x, 4*sys_clk_freq)
        pll.create_clkout(self.cd_sys4x_dqs, 4*sys_clk_freq, phase=90.0)
        pll.create_clkout(self.cd_clk200, 200e6)
        # pll.create_clkout(self.cd_clk1x, 100e6, phase=90.0)
        pll.create_clkout(self.cd_clk1x, 100e6)

        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_clk200)


class BaseSoC(SoCSDRAM):
    csr_map = {
        "ddrphy":    16,
    }
    csr_map.update(SoCSDRAM.csr_map)

    def __init__(self, **kwargs):
        platform = ac701.Platform(programmer='xc3sprog')
        sys_clk_freq = int(125e6)
        SoCSDRAM.__init__(self, platform, clk_freq=sys_clk_freq,
                         integrated_rom_size=0x8000,
                         integrated_sram_size=0x8000,
                          **kwargs)

        self.submodules.crg = _CRG(platform, sys_clk_freq)

        # sdram
        self.submodules.ddrphy = s7ddrphy.A7DDRPHY(platform.request("ddram"), sys_clk_freq=sys_clk_freq)
        sdram_module = MT8JTF12864(sys_clk_freq, "1:4")
        self.register_sdram(self.ddrphy,
                            sdram_module.geom_settings,
                            sdram_module.timing_settings)

# EthernetSoC ------------------------------------------------------------------------------------------

class EthernetSoC(BaseSoC):
    csr_map = {
        "ethphy": 18,
        "xadc": 19
        #        "ethmac": 19
    }
    csr_map.update(BaseSoC.csr_map)

    interrupt_map = {
        #        "ethmac": 3,
    }
    interrupt_map.update(BaseSoC.interrupt_map)

    mem_map = {
        "xadc": 0x30000000
        #        "ethmac": 0x30000000,  # (shadow @0xb0000000)
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, **kwargs):
        BaseSoC.__init__(self, **kwargs)
        self.create_qpll()
        self.submodules.ethphy = A7_1000BASEX(self.ethphy_qpll_channel,
                                              self.platform.request("sfp", 0),
                                              self.clk_freq)

        self.platform.add_period_constraint(self.crg.cd_sys.clk, 8.0)
        self.platform.add_period_constraint(self.ethphy.txoutclk, 16.)
        self.platform.add_period_constraint(self.ethphy.rxoutclk, 16.)
        # self.platform.add_period_constraint(self.crg.cd_clk1x, 13.)
        # self.platform.add_period_constraint(self.crg.cd_clk2x, 6.5)
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.ethphy.txoutclk, self.ethphy.rxoutclk)

        self.crg.cd_sys.clk.attr.add("keep")
        mac_address = 0x10e2d5000000
        ip_address = 0xc0a80132
        self.submodules.core = LiteEthUDPIPCore(self.ethphy, mac_address, ip_address, self.clk_freq)

    def create_qpll(self):
        qpll_settings = QPLLSettings(
            refclksel=0b111,
            fbdiv=4,
            fbdiv_45=5,
            refclk_div=1)
        qpll = QPLL(self.crg.cd_sys.clk, qpll_settings)
        self.submodules += qpll
        self.ethphy_qpll_channel = qpll.channels[0]


class EtherboneSoC(EthernetSoC):
    def __init__(self, **kwargs):
        EthernetSoC.__init__(self, **kwargs)
        self.submodules.etherbone = LiteEthEtherbone(self.core.udp, 1234, mode="master")
        self.add_wb_master(self.etherbone.wishbone.bus)

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on AC701")
    builder_args(parser)
    soc_sdram_args(parser)
    parser.add_argument("--with-ethernet", action="store_true",
                        help="enable Ethernet support")
    args = parser.parse_args()
    cls = EtherboneSoC if args.with_ethernet else BaseSoC
    soc = cls(**soc_sdram_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()
    # prog = soc.platform.create_programmer()
    # prog.load_bitstream("soc_ethernetsoc_ac701/gateware/top.bit")


if __name__ == "__main__":
    main()
