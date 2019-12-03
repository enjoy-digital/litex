#!/usr/bin/env python3

# This file is Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018 David Shah <dave@ds0.me>
# License: BSD

import argparse

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.boards.platforms import ulx3s

from litex.soc.cores.clock import *
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *

from litedram.modules import MT48LC16M16
from litedram.phy import GENSDRPHY

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_sys    = ClockDomain()
        self.clock_domains.cd_sys_ps = ClockDomain(reset_less=True)

        # # #

        self.cd_sys.clk.attr.add("keep")
        self.cd_sys_ps.clk.attr.add("keep")

        # clk / rst
        clk25 = platform.request("clk25")
        rst   = platform.request("rst")
        platform.add_period_constraint(clk25, 40.0)

        # pll
        self.submodules.pll = pll = ECP5PLL()
        self.comb += pll.reset.eq(rst)
        pll.register_clkin(clk25, 25e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq, phase=11)
        pll.create_clkout(self.cd_sys_ps, sys_clk_freq, phase=20)
        self.specials += AsyncResetSynchronizer(self.cd_sys, rst)

        # sdram clock
        self.comb += platform.request("sdram_clock").eq(self.cd_sys_ps.clk)

        # Stop ESP32 from resetting FPGA
        wifi_gpio0 = platform.request("wifi_gpio0")
        self.comb += wifi_gpio0.eq(1)

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCSDRAM):
    def __init__(self, device="LFE5U-45F", toolchain="diamond", **kwargs):
        platform = ulx3s.Platform(device=device, toolchain=toolchain)
        sys_clk_freq = int(50e6)

        # SoCSDRAM ---------------------------------------------------------------------------------
        SoCSDRAM.__init__(self, platform, clk_freq=sys_clk_freq,
            integrated_rom_size=0x8000,
            **kwargs)

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = _CRG(platform, sys_clk_freq)

        # SDR SDRAM --------------------------------------------------------------------------------
        if not self.integrated_main_ram_size:
            self.submodules.sdrphy = GENSDRPHY(platform.request("sdram"), cl=2)
            sdram_module = MT48LC16M16(sys_clk_freq, "1:1")
            self.register_sdram(self.sdrphy,
                geom_settings   = sdram_module.geom_settings,
                timing_settings = sdram_module.timing_settings)

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on ULX3S")
    parser.add_argument("--gateware-toolchain", dest="toolchain", default="diamond",
        help='gateware toolchain to use, diamond (default) or  trellis')
    parser.add_argument("--device", dest="device", default="LFE5U-45F",
        help='FPGA device, ULX3S can be populated with LFE5U-45F (default) or LFE5U-85F')
    builder_args(parser)
    soc_sdram_args(parser)
    args = parser.parse_args()

    soc = BaseSoC(device=args.device, toolchain=args.toolchain, **soc_sdram_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()

if __name__ == "__main__":
    main()
