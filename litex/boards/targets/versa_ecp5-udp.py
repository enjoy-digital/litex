#!/usr/bin/env python3

# This file is Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018-2019 David Shah <dave@ds0.me>
# License: BSD

import argparse
import sys

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.fhdl.decorators import ClockDomainsRenamer # RETO

from litex.boards.platforms import versa_ecp5

from litex.build.lattice.trellis import trellis_args, trellis_argdict

from litex.soc.cores.clock import *
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *

from litedram.modules import MT41K64M16
from litedram.phy import ECP5DDRPHY

from liteeth.common import stream, eth_udp_user_description, Port, convert_ip, eth_tty_description
from liteeth.core import LiteEthUDPIPCore
from liteeth.frontend.etherbone import LiteEthEtherbone
from liteeth.phy.ecp5rgmii import LiteEthPHYRGMII

from litex.soc.cores.uart import UARTWishboneBridge
from litescope import LiteScopeAnalyzer

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_init    = ClockDomain()
        self.clock_domains.cd_por     = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys     = ClockDomain()
        self.clock_domains.cd_sys2x   = ClockDomain()
        self.clock_domains.cd_sys2x_i = ClockDomain(reset_less=True)

        # # #

        self.stop = Signal()

        # Clk / Rst
        clk100 = platform.request("clk100")
        rst_n  = platform.request("rst_n")
        platform.add_period_constraint(clk100, 1e9/100e6)

        # Power on reset
        por_count = Signal(16, reset=2**16-1)
        por_done  = Signal()
        self.comb += self.cd_por.clk.eq(ClockSignal())
        self.comb += por_done.eq(por_count == 0)
        self.sync.por += If(~por_done, por_count.eq(por_count - 1))

        # PLL
        self.submodules.pll = pll = ECP5PLL()
        pll.register_clkin(clk100, 100e6)
        pll.create_clkout(self.cd_sys2x_i, 2*sys_clk_freq)
        pll.create_clkout(self.cd_init, 25e6)
        self.specials += [
            Instance("ECLKSYNCB",
                i_ECLKI = self.cd_sys2x_i.clk,
                i_STOP  = self.stop,
                o_ECLKO = self.cd_sys2x.clk),
            Instance("CLKDIVF",
                p_DIV     = "2.0",
                i_ALIGNWD = 0,
                i_CLKI    = self.cd_sys2x.clk,
                i_RST     = self.cd_sys2x.rst,
                o_CDIVX   = self.cd_sys.clk),
            AsyncResetSynchronizer(self.cd_init, ~por_done | ~pll.locked | ~rst_n),
            AsyncResetSynchronizer(self.cd_sys,  ~por_done | ~pll.locked | ~rst_n)
        ]

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCSDRAM):
    def __init__(self, sys_clk_freq=int(75e6), toolchain="trellis", **kwargs):
        platform = versa_ecp5.Platform(toolchain=toolchain)

        # SoCSDRAM ---------------------------------------------------------------------------------
        SoCSDRAM.__init__(self, platform, clk_freq=sys_clk_freq, **kwargs)

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = _CRG(platform, sys_clk_freq)

        # DDR3 SDRAM -------------------------------------------------------------------------------
        if not self.integrated_main_ram_size:
            self.submodules.ddrphy = ECP5DDRPHY(
                platform.request("ddram"),
                sys_clk_freq=sys_clk_freq)
            self.add_csr("ddrphy")
            self.add_constant("ECP5DDRPHY", None)
            self.comb += self.crg.stop.eq(self.ddrphy.init.stop)
            sdram_module = MT41K64M16(sys_clk_freq, "1:2")
            self.register_sdram(self.ddrphy,
                geom_settings   = sdram_module.geom_settings,
                timing_settings = sdram_module.timing_settings)

# EthernetSoC --------------------------------------------------------------------------------------

class EthernetSoC(BaseSoC):
    
    def add_udp_loopback(self, portnum, dw, depth, name=None):
        port = self.eth_core.udp.crossbar.get_port(portnum, dw, cd="sys2x_i")
        buf = ClockDomainsRenamer("sys2x_i")(stream.SyncFIFO(eth_udp_user_description(dw), depth//(dw//8), buffered=True))
        if name is None:
            self.submodules += buf
        else:
            setattr(self.submodules, name, buf)
        self.comb += Port.connect(port, buf)
        
    def __init__(self, sys_clk_freq=int(75e6), toolchain="trellis", **kwargs):
        BaseSoC.__init__(self, toolchain=toolchain, **kwargs)

        # Ethernet ---------------------------------------------------------------------------------
        # phy
        self.submodules.ethphy = ClockDomainsRenamer("sys2x_i")(LiteEthPHYRGMII(
            self.platform.request("eth_clocks"),
            self.platform.request("eth")))
        self.add_csr("ethphy")
        
        self.submodules.eth_core = ClockDomainsRenamer("sys2x_i")(LiteEthUDPIPCore(
            phy         = self.ethphy,
            mac_address = 0x10e2d5000001,
            ip_address  = "192.168.1.50",
            clk_freq    = int(2*sys_clk_freq),
            with_icmp   = True))

        self.add_udp_loopback(8000, 32, 128, "loopback_32")

        # etherbone - TODO, doesn't work yet
        # self.submodules.etherbone = LiteEthEtherbone(self.eth_core.udp, 1234)
        # self.add_wb_master(self.etherbone.wishbone.bus)

        # litescope - TODO, needs etherbone to work first
        # analyzer_signals = [
        #     self.loopback_32.sink
        # ]
        # self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals, 4096, csr_csv="tools/analyzer.csv")
        # self.add_csr("analyzer")
        
        # timing constraints
        self.platform.add_period_constraint(self.ethphy.crg.cd_eth_rx.clk, 1e9/125e6)
        self.platform.add_period_constraint(self.ethphy.crg.cd_eth_tx.clk, 1e9/125e6)
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.ethphy.crg.cd_eth_rx.clk,
            self.ethphy.crg.cd_eth_tx.clk)

# Build --------------------------------------------------------------------------------------------

def build():
    parser = argparse.ArgumentParser(description="LiteX SoC on Versa ECP5")
    parser.add_argument("--gateware-toolchain", dest="toolchain", default="diamond",
        help='gateware toolchain to use, diamond (default) or  trellis')
    builder_args(parser)
    soc_sdram_args(parser)
    trellis_args(parser)
    parser.add_argument("--sys-clk-freq", default=75e6,
                        help="system clock frequency (default=75MHz)")
    parser.add_argument("--with-ethernet", action="store_true",
                        help="enable Ethernet support")
    args = parser.parse_args()

    cls = EthernetSoC if args.with_ethernet else BaseSoC
    soc = cls(toolchain=args.toolchain, sys_clk_freq=int(float(args.sys_clk_freq)), **soc_sdram_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder_kargs = {}
    if args.toolchain == "trellis":
        builder_kargs == trellis_argdict(args)
    builder.build(**builder_kargs)

def load():
    import os
    f = open("ecp5-versa5g.cfg", "w")
    f.write(
"""
interface ftdi
ftdi_vid_pid 0x0403 0x6010
ftdi_channel 0
ftdi_layout_init 0xfff8 0xfffb
reset_config none
adapter_khz 25000
jtag newtap ecp5 tap -irlen 8 -expected-id 0x81112043
""")
    f.close()
    os.system("openocd -f ecp5-versa5g.cfg -c \"transport select jtag; init; svf ./soc_ethernetsoc_versa_ecp5/gateware/top.svf; exit\"")
    exit()
    
if __name__ == "__main__":
    print(len(sys.argv))
    print(sys.argv[0])
    if (len(sys.argv) == 2 and sys.argv[1] == 'load'):
        load()
    else:
        build()
