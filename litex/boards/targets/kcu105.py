#!/usr/bin/env python3

# This file is Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import argparse

from migen import *

from litex.boards.platforms import kcu105

from litex.soc.cores.clock import *
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *

from litedram.modules import EDY4016A
from litedram.phy import usddrphy

from liteeth.phy.ku_1000basex import KU_1000BASEX
from liteeth.mac import LiteEthMAC

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys4x = ClockDomain(reset_less=True)
        self.clock_domains.cd_clk200 = ClockDomain()
        self.clock_domains.cd_ic = ClockDomain()

        # # #

        self.cd_sys.clk.attr.add("keep")
        self.cd_sys4x.clk.attr.add("keep")

        self.submodules.pll = pll = USMMCM(speedgrade=-2)
        self.comb += pll.reset.eq(platform.request("cpu_reset"))
        self.clock_domains.cd_pll4x = ClockDomain(reset_less=True)
        pll.register_clkin(platform.request("clk125"), 125e6)
        pll.create_clkout(self.cd_pll4x, sys_clk_freq*4, buf=None, with_reset=False)
        pll.create_clkout(self.cd_clk200, 200e6, with_reset=False)

        self.specials += [
            Instance("BUFGCE_DIV", name="main_bufgce_div",
                p_BUFGCE_DIVIDE=4,
                i_CE=1, i_I=self.cd_pll4x.clk, o_O=self.cd_sys.clk),
            Instance("BUFGCE", name="main_bufgce",
                i_CE=1, i_I=self.cd_pll4x.clk, o_O=self.cd_sys4x.clk),
            AsyncResetSynchronizer(self.cd_clk200, ~pll.locked),
        ]

        ic_reset_counter = Signal(max=64, reset=63)
        ic_reset = Signal(reset=1)
        self.sync.clk200 += \
            If(ic_reset_counter != 0,
                ic_reset_counter.eq(ic_reset_counter - 1)
            ).Else(
                ic_reset.eq(0)
            )
        ic_rdy = Signal()
        ic_rdy_counter = Signal(max=64, reset=63)
        self.cd_sys.rst.reset = 1
        self.comb += self.cd_ic.clk.eq(self.cd_sys.clk)
        self.sync.ic += [
            If(ic_rdy,
                If(ic_rdy_counter != 0,
                    ic_rdy_counter.eq(ic_rdy_counter - 1)
                ).Else(
                    self.cd_sys.rst.eq(0)
                )
            )
        ]
        self.specials += [
            Instance("IDELAYCTRL", p_SIM_DEVICE="ULTRASCALE",
                     i_REFCLK=ClockSignal("clk200"), i_RST=ic_reset,
                     o_RDY=ic_rdy),
            AsyncResetSynchronizer(self.cd_ic, ic_reset)
        ]

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCSDRAM):
    def __init__(self, sys_clk_freq=int(125e6), integrated_rom_size=0x8000, **kwargs):
        platform = kcu105.Platform()
        SoCSDRAM.__init__(self, platform, clk_freq=sys_clk_freq,
                         integrated_rom_size=integrated_rom_size,
                         integrated_sram_size=0x8000,
                          **kwargs)

        self.submodules.crg = _CRG(platform, sys_clk_freq)

        # sdram
        self.submodules.ddrphy = usddrphy.USDDRPHY(platform.request("ddram"), memtype="DDR4", sys_clk_freq=sys_clk_freq)
        self.add_csr("ddrphy")
        self.add_constant("USDDRPHY", None)
        sdram_module = EDY4016A(sys_clk_freq, "1:4")
        self.register_sdram(self.ddrphy,
                            sdram_module.geom_settings,
                            sdram_module.timing_settings)


# EthernetSoC ------------------------------------------------------------------------------------------

class EthernetSoC(BaseSoC):
    mem_map = {
        "ethmac": 0xb0000000,
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, **kwargs):
        BaseSoC.__init__(self, integrated_rom_size=0x10000, **kwargs)

        self.comb += self.platform.request("sfp_tx_disable_n", 0).eq(1)
        self.submodules.ethphy = KU_1000BASEX(self.crg.cd_clk200.clk,
            self.platform.request("sfp", 0), sys_clk_freq=self.clk_freq)
        self.add_csr("ethphy")
        self.submodules.ethmac = LiteEthMAC(phy=self.ethphy, dw=32,
            interface="wishbone", endianness=self.cpu.endianness)
        self.add_wb_slave(self.mem_map["ethmac"], self.ethmac.bus, 0x2000)
        self.add_memory_region("ethmac", self.mem_map["ethmac"], 0x2000, io_region=True)
        self.add_csr("ethmac")
        self.add_interrupt("ethmac")

        self.ethphy.cd_eth_rx.clk.attr.add("keep")
        self.ethphy.cd_eth_tx.clk.attr.add("keep")
        self.platform.add_period_constraint(self.ethphy.cd_eth_rx.clk, 1e9/125e6)
        self.platform.add_period_constraint(self.ethphy.cd_eth_tx.clk, 1e9/125e6)
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.ethphy.cd_eth_rx.clk,
            self.ethphy.cd_eth_tx.clk)

        self.platform.add_platform_command("set_property SEVERITY {{Warning}} [get_drc_checks REQP-1753]")

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on KCU105")
    builder_args(parser)
    soc_sdram_args(parser)
    parser.add_argument("--with-ethernet", action="store_true",
                        help="enable Ethernet support")
    args = parser.parse_args()

    cls = EthernetSoC if args.with_ethernet else BaseSoC
    soc = cls(**soc_sdram_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()


if __name__ == "__main__":
    main()
