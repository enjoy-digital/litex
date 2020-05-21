#!/usr/bin/env python3

# This file is Copyright (c) 2019 Sean Cross <sean@xobs.io>
# This file is Copyright (c) 2018 David Shah <dave@ds0.me>
# This file is Copyright (c) 2020 Piotr Esden-Tempski <piotr@esden.net>
# This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

# The iCEBreaker is the first open source iCE40 FPGA development board designed for teachers and
# students: https://www.crowdsupply.com/1bitsquared/icebreaker-fpga

# This target file provides a minimal LiteX SoC for the iCEBreaker with a CPU, its ROM (in SPI Flash),
# its SRAM, close to the others LiteX targets. A more complete example of LiteX SoC for the iCEBreaker
# with more features, examples to run C/Rust code on the RISC-V CPU and documentation can be found
# at: https://github.com/icebreaker-fpga/icebreaker-litex-examples

import os
import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.boards.platforms import icebreaker

from litex.soc.cores.up5kspram import Up5kSPRAM
from litex.soc.cores.spi_flash import SpiFlash
from litex.soc.cores.clock import iCE40PLL
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *

kB = 1024
mB = 1024*kB

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_por = ClockDomain()

        # # #

        # Clocking
        clk12 = platform.request("clk12")
        rst_n = platform.request("user_btn_n")
        if sys_clk_freq == 12e6:
            self.comb += self.cd_sys.clk.eq(clk12)
        else:
            self.submodules.pll = pll = iCE40PLL(primitive="SB_PLL40_PAD")
            pll.register_clkin(clk12, 12e6)
            pll.create_clkout(self.cd_sys, sys_clk_freq)
        platform.add_period_constraint(self.cd_sys.clk, 1e9/sys_clk_freq)

        # Power On Reset
        por_cycles  = 4096
        por_counter = Signal(log2_int(por_cycles), reset=por_cycles-1)
        self.comb += self.cd_por.clk.eq(self.cd_sys.clk)
        platform.add_period_constraint(self.cd_por.clk, 1e9/sys_clk_freq)
        self.sync.por += If(por_counter != 0, por_counter.eq(por_counter - 1))
        self.specials += AsyncResetSynchronizer(self.cd_por, ~rst_n)
        self.specials += AsyncResetSynchronizer(self.cd_sys, (por_counter != 0))

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    SoCCore.mem_map = {
        "sram":             0x10000000,
        "spiflash":         0x20000000,
        "csr":              0xf0000000,
    }
    def __init__(self, bios_flash_offset, **kwargs):
        sys_clk_freq = int(24e6)
        platform     = icebreaker.Platform()

        # Disable Integrated ROM/SRAM since too large for iCE40 and UP5K has specific SPRAM.
        kwargs["integrated_sram_size"] = 0
        kwargs["integrated_rom_size"]  = 0

        # Set CPU variant / reset address
        kwargs["cpu_reset_address"] = self.mem_map["spiflash"] + bios_flash_offset

        # SoCCore ----------------------------------------------------------------------------------
        SoCCore.__init__(self, platform, sys_clk_freq, **kwargs)

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = _CRG(platform, sys_clk_freq)

        # 128KB SPRAM (used as SRAM) ---------------------------------------------------------------
        self.submodules.spram = Up5kSPRAM(size=64*kB)
        self.register_mem("sram", self.mem_map["sram"], self.spram.bus, 64*kB)

        # SPI Flash --------------------------------------------------------------------------------
        self.submodules.spiflash = SpiFlash(platform.request("spiflash4x"), dummy=6, endianness="little")
        self.register_mem("spiflash", self.mem_map["spiflash"], self.spiflash.bus, size=16*mB)
        self.add_csr("spiflash")

        # Add ROM linker region --------------------------------------------------------------------
        self.add_memory_region("rom", self.mem_map["spiflash"] + bios_flash_offset, 32*kB, type="cached+linker")

        # Leds -------------------------------------------------------------------------------------
        counter = Signal(32)
        self.sync += counter.eq(counter + 1)
        self.comb += platform.request("user_ledr_n").eq(counter[26])
        self.comb += platform.request("user_ledg_n").eq(~counter[26])

# Flash --------------------------------------------------------------------------------------------

def flash(bios_flash_offset):
    from litex.build.lattice.programmer import IceStormProgrammer
    prog = IceStormProgrammer()
    prog.flash(bios_flash_offset, "soc_basesoc_icebreaker/software/bios/bios.bin")
    prog.flash(0x00000000,        "soc_basesoc_icebreaker/gateware/top.bin")
    exit()

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on iCEBreaker")
    parser.add_argument("--build",             action="store_true", help="Build bitstream")
    parser.add_argument("--load",              action="store_true", help="Load bitstream")
    parser.add_argument("--bios-flash-offset", default=0x40000,     help="BIOS offset in SPI Flash")
    parser.add_argument("--flash",             action="store_true", help="Flash Bitstream")
    builder_args(parser)
    soc_core_args(parser)
    args = parser.parse_args()

    soc     = BaseSoC(args.bios_flash_offset, **soc_core_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build(run=args.build)

    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(os.path.join(builder.gateware_dir, soc.build_name + ".bin"))

    if args.flash:
        flash(args.bios_flash_offset)

if __name__ == "__main__":
    main()
