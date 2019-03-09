#!/usr/bin/env python3

import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.boards.platforms import versa_ecp5

from litex.soc.cores.clock import *
from litex.soc.integration.soc_core import mem_decoder
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *

from litedram.modules import MT41K64M16
from litedram.phy import ECP5DDRPHY

from liteeth.phy.ecp5rgmii import LiteEthPHYRGMII
from liteeth.core.mac import LiteEthMAC

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_init = ClockDomain()
        self.clock_domains.cd_por = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys2x = ClockDomain()
        self.clock_domains.cd_sys2x_i = ClockDomain(reset_less=True)

        # # #

        self.stop = Signal()

        # clk / rst
        clk100 = platform.request("clk100")
        rst_n = platform.request("rst_n")
        platform.add_period_constraint(clk100, 10.0)

        # power on reset
        por_count = Signal(16, reset=2**16-1)
        por_done = Signal()
        self.comb += self.cd_por.clk.eq(ClockSignal())
        self.comb += por_done.eq(por_count == 0)
        self.sync.por += If(~por_done, por_count.eq(por_count - 1))

        # pll
        self.submodules.pll = pll = ECP5PLL()
        pll.register_clkin(clk100, 100e6)
        pll.create_clkout(self.cd_sys2x_i, 2*sys_clk_freq)
        pll.create_clkout(self.cd_init, 25e6)
        self.specials += [
            Instance("ECLKSYNCB",
                i_ECLKI=self.cd_sys2x_i.clk,
                i_STOP=self.stop,
                o_ECLKO=self.cd_sys2x.clk),
            Instance("CLKDIVF",
                p_DIV="2.0",
                i_ALIGNWD=0,
                i_CLKI=self.cd_sys2x.clk,
                i_RST=self.cd_sys2x.rst,
                o_CDIVX=self.cd_sys.clk),
            AsyncResetSynchronizer(self.cd_init, ~por_done | ~pll.locked | ~rst_n),
            AsyncResetSynchronizer(self.cd_sys, ~por_done | ~pll.locked | ~rst_n)
        ]

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCSDRAM):
    csr_map = {
        "ddrphy":    16,
    }
    csr_map.update(SoCSDRAM.csr_map)
    def __init__(self, toolchain="diamond", **kwargs):
        platform = versa_ecp5.Platform(toolchain=toolchain)
        sys_clk_freq = int(75e6)
        SoCSDRAM.__init__(self, platform, clk_freq=sys_clk_freq,
                          integrated_rom_size=0x8000,
                          **kwargs)

        # crg
        crg = _CRG(platform, sys_clk_freq)
        self.submodules.crg = crg

        # sdram
        self.submodules.ddrphy = ECP5DDRPHY(
            platform.request("ddram"),
            sys_clk_freq=sys_clk_freq)
        self.add_constant("ECP5DDRPHY", None)
        self.comb += crg.stop.eq(self.ddrphy.init.stop)
        sdram_module = MT41K64M16(sys_clk_freq, "1:2")
        self.register_sdram(self.ddrphy,
            sdram_module.geom_settings,
            sdram_module.timing_settings)

# EthernetSoC --------------------------------------------------------------------------------------

class EthernetSoC(BaseSoC):
    csr_map = {
        "ethphy": 18,
        "ethmac": 19
    }
    csr_map.update(BaseSoC.csr_map)

    interrupt_map = {
        "ethmac": 3,
    }
    interrupt_map.update(BaseSoC.interrupt_map)

    mem_map = {
        "ethmac": 0x30000000,  # (shadow @0xb0000000)
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, toolchain="diamond", **kwargs):
        BaseSoC.__init__(self, toolchain=toolchain, **kwargs)

        self.submodules.ethphy = LiteEthPHYRGMII(
            self.platform.request("eth_clocks"),
            self.platform.request("eth"))
        self.submodules.ethmac = LiteEthMAC(phy=self.ethphy, dw=32,
            interface="wishbone", endianness=self.cpu.endianness)
        self.add_wb_slave(mem_decoder(self.mem_map["ethmac"]), self.ethmac.bus)
        self.add_memory_region("ethmac", self.mem_map["ethmac"] | self.shadow_base, 0x2000)

        self.ethphy.crg.cd_eth_rx.clk.attr.add("keep")
        self.ethphy.crg.cd_eth_tx.clk.attr.add("keep")
        self.platform.add_period_constraint(self.ethphy.crg.cd_eth_rx.clk, 1e9/125e6)
        self.platform.add_period_constraint(self.ethphy.crg.cd_eth_tx.clk, 1e9/125e6)

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on Versa ECP5")
    parser.add_argument("--gateware-toolchain", dest="toolchain", default="diamond",
        help='gateware toolchain to use, diamond (default) or  trellis')
    builder_args(parser)
    soc_sdram_args(parser)
    parser.add_argument("--with-ethernet", action="store_true",
                        help="enable Ethernet support")
    args = parser.parse_args()

    cls = EthernetSoC if args.with_ethernet else BaseSoC
    soc = cls(args.toolchain, **soc_sdram_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()

if __name__ == "__main__":
    main()
