#!/usr/bin/env python3

import argparse
import importlib

from migen import *
from litex.boards.platforms import sim
from migen.genlib.io import CRG

from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *
from litex.soc.cores import uart
from litex.soc.cores.sdram.settings import PhySettings, IS42S16160
from litex.soc.cores.sdram.model import SDRAMPHYModel


class BaseSoC(SoCSDRAM):
    def __init__(self, **kwargs):
        platform = sim.Platform()
        SoCSDRAM.__init__(self, platform,
            clk_freq=int((1/(platform.default_clk_period))*1000000000),
            integrated_rom_size=0x8000,
            with_uart=False,
            **kwargs)
        self.submodules.crg = CRG(platform.request(platform.default_clk_name))

        self.submodules.uart_phy = uart.RS232PHYModel(platform.request("serial"))
        self.submodules.uart = uart.UART(self.uart_phy)

        if not self.integrated_main_ram_size:
            sdram_module = IS42S16160(self.clk_freq)
            phy_settings = PhySettings(
                memtype="SDR",
                dfi_databits=1*16,
                nphases=1,
                rdphase=0,
                wrphase=0,
                rdcmdphase=0,
                wrcmdphase=0,
                cl=2,
                read_latency=4,
                write_latency=0
            )
            self.submodules.sdrphy = SDRAMPHYModel(sdram_module, phy_settings)
            self.register_sdram(self.sdrphy, "minicon",
                                sdram_module.geom_settings, sdram_module.timing_settings)



def main():
    parser = argparse.ArgumentParser(description="Generic LiteX SoC Simulation")
    builder_args(parser)
    soc_sdram_args(parser)
    args = parser.parse_args()

    soc = BaseSoC(**soc_sdram_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()


if __name__ == "__main__":
    main()
