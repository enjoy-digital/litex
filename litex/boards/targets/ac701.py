#!/usr/bin/env python3

import argparse

from migen import ClockDomain, Signal, Instance, Module

from litex.boards.platforms import ac701

from litex.soc.cores.clock import S7MMCM, S7IDELAYCTRL
from litex.soc.integration.soc_sdram import (SoCSDRAM, soc_sdram_args,
                                             soc_sdram_argdict)
from litex.soc.integration.builder import (builder_args, Builder,
                                           builder_argdict)
# from litex.soc.integration.soc_core import mem_decoder

from litedram.modules import MT8JTF12864
from litedram.phy import s7ddrphy

from liteeth.phy.a7_gtp import QPLLSettings, QPLL
from liteeth.phy.a7_1000basex import A7_1000BASEX
from liteeth.phy.s7rgmii import LiteEthPHYRGMII
from liteeth.core import LiteEthUDPIPCore

from liteeth.frontend.etherbone import LiteEthEtherbone
from litex.soc.interconnect.csr import AutoCSR, CSRStatus


class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys4x = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys4x_dqs = ClockDomain(reset_less=True)
        self.clock_domains.cd_clk200 = ClockDomain()
        self.clock_domains.cd_clk1x = ClockDomain()
        self.clock_domains.cd_clk2x = ClockDomain()

        self.clk125 = Signal()
        clk125_ds = platform.request("gtp_refclk")
        self.specials += Instance("IBUFDS_GTE2",
                                  i_CEB=0,
                                  i_I=clk125_ds.p, i_IB=clk125_ds.n,
                                  o_O=self.clk125)

        self.submodules.pll = pll = S7MMCM(speedgrade=-2)
        self.comb += platform.request("sfp_mgt_clk_sel0", 0).eq(0)
        self.comb += platform.request("sfp_mgt_clk_sel1", 0).eq(0)
        self.comb += platform.request("sfp_tx_disable_n", 0).eq(0)
        self.comb += pll.reset.eq(platform.request("cpu_reset"))
        pll.register_clkin(self.clk125, 125e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)
        pll.create_clkout(self.cd_sys4x, 4*sys_clk_freq)
        pll.create_clkout(self.cd_sys4x_dqs, 4*sys_clk_freq, phase=90.0)
        pll.create_clkout(self.cd_clk200, 200e6)
        pll.create_clkout(self.cd_clk1x, 100e6)

        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_clk200)


class BaseSoC(SoCSDRAM):
    csr_map = {
        "ddrphy":    16,
    }
    csr_map.update(SoCSDRAM.csr_map)

    def __init__(self, clk_freq=125e6, **kwargs):
        platform = ac701.Platform(programmer='xc3sprog')
        sys_clk_freq = int(clk_freq)
        SoCSDRAM.__init__(self, platform, clk_freq=sys_clk_freq,
                          integrated_rom_size=0x8000,
                          integrated_sram_size=0x8000,
                          **kwargs)

        self.submodules.crg = _CRG(platform, sys_clk_freq)

        # sdram
        self.submodules.ddrphy = s7ddrphy.A7DDRPHY(platform.request("ddram"),
                                                   sys_clk_freq=sys_clk_freq)
        sdram_module = MT8JTF12864(sys_clk_freq, "1:4")
        self.register_sdram(self.ddrphy,
                            sdram_module.geom_settings,
                            sdram_module.timing_settings)


class Debug(Module, AutoCSR):
    def __init__(self, lock, tx_init_done, test):
        self.foo_counter = CSRStatus(26)
        self.lock = CSRStatus(1)
        self.tx_init_done = CSRStatus(1)
        self.test = CSRStatus(1)
        counter = Signal(26)
        self.sync.eth_tx += [counter.eq(counter + 1),
                             self.foo_counter.status.eq(counter)]
        self.comb += [
            self.tx_init_done.status.eq(tx_init_done),
            self.lock.status.eq(lock),
            self.test.status.eq(test)
        ]


class EthernetSoC(BaseSoC):
    csr_map = {
        "ethphy": 18,
        "xadc": 19,
        "Debug": 20,
        # "ethmac": 21
    }
    csr_map.update(BaseSoC.csr_map)

    interrupt_map = {
        # "ethmac": 3,
    }
    interrupt_map.update(BaseSoC.interrupt_map)

    mem_map = {
        # "xadc": 0x30000000,
        # "ethmac": 0x30000000,  # (shadow @0xb0000000)
    }
    mem_map.update(BaseSoC.mem_map)

    def setup_sfp_phy(self):
        self.create_qpll()
        self.submodules.ethphy = A7_1000BASEX(self.ethphy_qpll_channel,
                                              self.platform.request("sfp", 0),
                                              self.clk_freq)
        self.platform.add_period_constraint(self.crg.cd_sys.clk, 8.0)
        self.platform.add_period_constraint(self.ethphy.txoutclk, 16.)
        self.platform.add_period_constraint(self.ethphy.rxoutclk, 16.)
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.ethphy.txoutclk, self.ethphy.rxoutclk)

    def setup_rgmii_phy(self):
        self.submodules.ethphy = LiteEthPHYRGMII(self.platform.request("eth_clocks"),
                                                 self.platform.request("eth"))
        # self.add_wb_slave(mem_decoder(self.mem_map["ethmac"]), self.ethmac.bus)
        # self.add_memory_region("ethmac", self.mem_map["ethmac"] | self.shadow_base, 0x2000)

        self.crg.cd_sys.clk.attr.add("keep")
        self.ethphy.crg.cd_eth_rx.clk.attr.add("keep")
        self.ethphy.crg.cd_eth_tx.clk.attr.add("keep")
        self.platform.add_period_constraint(self.crg.cd_sys.clk, 8.0)
        self.platform.add_period_constraint(self.ethphy.crg.cd_eth_rx.clk, 8.0)
        self.platform.add_period_constraint(self.ethphy.crg.cd_eth_tx.clk, 8.0)
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.ethphy.crg.cd_eth_rx.clk,
            self.ethphy.crg.cd_eth_tx.clk)

    def __init__(self, use_sfp=True, **kwargs):
        BaseSoC.__init__(self, **kwargs)
        if use_sfp:
            self.setup_sfp_phy()
        else:
            self.setup_rgmii_phy()
        self.crg.cd_sys.clk.attr.add("keep")
        mac_address = 0x10e2d5000000
        ip_address = 0xc0a80132
        self.submodules.core = LiteEthUDPIPCore(self.ethphy, mac_address,
                                                ip_address, self.clk_freq)
        # self.submodules.Debug = Debug(self.ethphy_qpll_channel.lock,
        #                               self.ethphy.tx_init.done,
        #                               self.ethphy.tx_init.tx_reset)

    def create_qpll(self):
        qpll_settings = QPLLSettings(
            refclksel=0b001,
            fbdiv=4,
            fbdiv_45=5,
            refclk_div=1)

        qpll = QPLL(self.crg.clk125, qpll_settings)
        self.submodules += qpll
        self.ethphy_qpll_channel = qpll.channels[0]


class EtherboneSoC(EthernetSoC):
    def __init__(self, **kwargs):
        EthernetSoC.__init__(self, **kwargs)
        self.submodules.etherbone = LiteEthEtherbone(self.core.udp, 1234,
                                                     mode="master")
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


if __name__ == "__main__":
    main()
