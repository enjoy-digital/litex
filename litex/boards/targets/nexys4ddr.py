#!/usr/bin/env python3

# This file is Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import os
import argparse

from migen import *

from litex.boards.platforms import nexys4ddr

from litex.soc.cores.clock import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *
from litex.soc.cores.led import LedChaser

from litedram.modules import MT47H64M16
from litedram.phy import s7ddrphy

from liteeth.phy.rmii import LiteEthPHYRMII

from litesdcard.phy import SDPHY
from litesdcard.clocker import SDClockerS7
from litesdcard.core import SDCore
from litesdcard.bist import BISTBlockGenerator, BISTBlockChecker
from litesdcard.data import SDDataReader, SDDataWriter
from litex.soc.cores.timer import Timer
from litex.soc.interconnect import wishbone

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_sys       = ClockDomain()
        self.clock_domains.cd_sys2x     = ClockDomain(reset_less=True)
        self.clock_domains.cd_sys2x_dqs = ClockDomain(reset_less=True)
        self.clock_domains.cd_clk200    = ClockDomain()
        self.clock_domains.cd_eth       = ClockDomain()

        # # #

        self.submodules.pll = pll = S7MMCM(speedgrade=-1)
        self.comb += pll.reset.eq(~platform.request("cpu_reset"))
        pll.register_clkin(platform.request("clk100"), 100e6)
        pll.create_clkout(self.cd_sys,       sys_clk_freq)
        pll.create_clkout(self.cd_sys2x,     2*sys_clk_freq)
        pll.create_clkout(self.cd_sys2x_dqs, 2*sys_clk_freq, phase=90)
        pll.create_clkout(self.cd_clk200,    200e6)
        pll.create_clkout(self.cd_eth,       50e6)

        self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_clk200)

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    mem_map = {**SoCCore.mem_map, **{
            "sdread":       0x80002000, # len: 0x200
            "sdwrite":      0x80002200, # len: 0x200
        }}
    def __init__(self, sys_clk_freq=int(75e6), with_ethernet=False, **kwargs):
        platform = nexys4ddr.Platform()

        # SoCCore ----------------------------------_-----------------------------------------------
        SoCCore.__init__(self, platform, clk_freq=sys_clk_freq, **kwargs)

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = _CRG(platform, sys_clk_freq)

        # DDR2 SDRAM -------------------------------------------------------------------------------
        if not self.integrated_main_ram_size:
            self.submodules.ddrphy = s7ddrphy.A7DDRPHY(platform.request("ddram"),
                memtype      = "DDR2",
                nphases      = 2,
                sys_clk_freq = sys_clk_freq)
            self.add_csr("ddrphy")
            self.add_sdram("sdram",
                phy                     = self.ddrphy,
                module                  = MT47H64M16(sys_clk_freq, "1:2"),
                origin                  = self.mem_map["main_ram"],
                size                    = kwargs.get("max_sdram_size", 0x40000000),
                l2_cache_size           = kwargs.get("l2_size", 8192),
                l2_cache_min_data_width = kwargs.get("min_l2_data_width", 128),
                l2_cache_reverse        = True
            )

        # Ethernet ---------------------------------------------------------------------------------
        if with_ethernet:
            self.submodules.ethphy = LiteEthPHYRMII(
                clock_pads = self.platform.request("eth_clocks"),
                pads       = self.platform.request("eth"))
            self.add_csr("ethphy")
            self.add_ethernet(phy=self.ethphy)

        # Leds -------------------------------------------------------------------------------------
        self.submodules.leds = LedChaser(
            pads         = Cat(*[platform.request("user_led", i) for i in range(16)]),
            sys_clk_freq = sys_clk_freq)
        self.add_csr("leds")

    def add_sdcard(self, memory_size=512, memory_width=32):
        sdcard_pads = self.platform.request("sdcard")
        if hasattr(sdcard_pads, "rst"):
            self.comb += sdcard_pads.rst.eq(0)
        self.submodules.sdclk = SDClockerS7(sys_clk_freq=self.sys_clk_freq)
        self.submodules.sdphy = SDPHY(sdcard_pads, self.platform.device)
        self.submodules.sdcore = SDCore(self.sdphy, csr_data_width=self.csr_data_width)
        self.submodules.sdtimer = Timer()
        self.add_csr("sdclk")
        self.add_csr("sdphy")
        self.add_csr("sdcore")
        self.add_csr("sdtimer")

        # SD Card data reader

        sdread_mem = Memory(memory_width, memory_size//4)
        sdread_sram = FullMemoryWE()(wishbone.SRAM(sdread_mem, read_only=True))
        self.submodules += sdread_sram

        self.add_wb_slave(self.mem_map["sdread"], sdread_sram.bus, memory_size)
        self.add_memory_region("sdread", self.mem_map["sdread"], memory_size)

        sdread_port = sdread_sram.mem.get_port(write_capable=True);
        self.specials += sdread_port
        self.submodules.sddatareader = SDDataReader(port=sdread_port, endianness=self.cpu.endianness)
        self.add_csr("sddatareader")
        self.comb += self.sdcore.source.connect(self.sddatareader.sink),

        # SD Card data writer

        sdwrite_mem = Memory(memory_width, memory_size//4)
        sdwrite_sram = FullMemoryWE()(wishbone.SRAM(sdwrite_mem, read_only=False))
        self.submodules += sdwrite_sram

        self.add_wb_slave(self.mem_map["sdwrite"], sdwrite_sram.bus, memory_size)
        self.add_memory_region("sdwrite", self.mem_map["sdwrite"], memory_size)

        sdwrite_port = sdwrite_sram.mem.get_port(write_capable=False, async_read=True, mode=READ_FIRST);
        self.specials += sdwrite_port
        self.submodules.sddatawriter = SDDataWriter(port=sdwrite_port, endianness=self.cpu.endianness)
        self.add_csr("sddatawriter")
        self.comb += self.sddatawriter.source.connect(self.sdcore.sink),

        self.platform.add_period_constraint(self.sdclk.cd_sd.clk, period_ns(self.sys_clk_freq))
        self.platform.add_period_constraint(self.sdclk.cd_sd_fb.clk, period_ns(self.sys_clk_freq))
        self.platform.add_false_path_constraints(
            self.crg.cd_sys.clk,
            self.sdclk.cd_sd.clk,
            self.sdclk.cd_sd_fb.clk)

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on Nexys4DDR")
    parser.add_argument("--build", action="store_true", help="Build bitstream")
    parser.add_argument("--load",  action="store_true", help="Load bitstream")
    builder_args(parser)
    soc_sdram_args(parser)
    parser.add_argument("--sys-clk-freq",  default=75e6,          help="System clock frequency (default=75MHz)")
    parser.add_argument("--with-ethernet", action="store_true",   help="Enable Ethernet support")
    parser.add_argument("--with-spi-sdcard", action="store_true", help="enable SPI-mode SDCard support")
    parser.add_argument("--with-sdcard", action="store_true",     help="enable SDCard support")
    args = parser.parse_args()

    soc = BaseSoC(sys_clk_freq=int(float(args.sys_clk_freq)),
        with_ethernet=args.with_ethernet,
        **soc_sdram_argdict(args))
    if args.with_spi_sdcard:
        soc.add_spi_sdcard()
    if args.with_sdcard:
        if args.with_spi_sdcard:
            raise ValueError("'--with-spi-sdcard' and '--with-sdcard' are mutually exclusive!")
        soc.add_sdcard()
    builder = Builder(soc, **builder_argdict(args))
    builder.build(run=args.build)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(os.path.join(builder.gateware_dir, soc.build_name + ".bit"))

if __name__ == "__main__":
    main()
