"""
Target support for the Digilent Cmod A7 Board
Inherit from the BaseSoC class in your design
"""
from migen import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.cores import spi_flash
from litex.soc.cores.clock import S7MMCM
import argparse
import importlib
from pprint import pprint


class NamespaceView(object):
    """ hack to address a dict() with . notation """
    def __init__(self, d):
        self.__dict__ = d


class _CRG(Module):
    """
    clock and reset generator
    clk should be a 12 MHz clock
    creates a cd_sys ClockDomain of clk_freq Hz
    """
    def __init__(self, clk, clk_freq=int(100e6)):
        self.clock_domains.cd_sys = ClockDomain()
        # self.clock_domains.cd_clk200 = ClockDomain()
        self.submodules.mmcm = mmcm = S7MMCM(speedgrade=-1)
        mmcm.register_clkin(clk, 12e6)
        # create_clkout also takes care of generating BUFG / BUFR instances
        mmcm.create_clkout(self.cd_sys, clk_freq)
        # mmcm.create_clkout(self.cd_clk200, 200e6)
        # self.submodules.idelayctrl = S7IDELAYCTRL(self.cd_clk200)


class BaseSoC(SoCCore):
    def basesoc_args(parser):
        soc_core_args(parser)
        parser.add_argument("--clk_freq", type=int, default=int(100e6),
                            help="Clock frequency [Hz]")
        parser.add_argument("--platform", default="litex.boards.platforms.cmod_a7",
                            help="Hardware platform module name")
        parser.add_argument("--spiflash", default="None",
                            choices=["None", "spiflash_1x", "spiflash_4x"],
                            help="SPI flash protocol")

    def __init__(self, **kwargs):
        pprint(kwargs)

        # Find the platform module
        platform = importlib.import_module(kwargs["platform"]).Platform()
        print("platform", platform)
        self.platform = kwargs["platform"] = platform
        # Add reset and clocking
        if "crg" in kwargs:
            self.submodules.crg = kwargs["crg"](
                platform.request("sys_clk"),
                kwargs["clk_freq"]
            )
        else:
            self.submodules.crg = _CRG(
                platform.request("clk12"),
                kwargs["clk_freq"]
            )
        self.addMemories(**kwargs)
        SoCCore.__init__(self, **kwargs)

    def addMemories(self, **kwargs):
        # spi flash
        if kwargs["spiflash"] != "None":
            csr_map_update(SoCCore.csr_map, ["spiflash"])
            # (default shadow @0xa0000000)
            self.mem_map.update({"spiflash": 0x20000000})
            spiflash_pads = platform.request(kwargs["spiflash"])
            spiflash_pads.clk = Signal()
            self.specials += Instance(
                "STARTUPE2",
                i_CLK=0, i_GSR=0, i_GTS=0, i_KEYCLEARB=0, i_PACK=0,
                i_USRCCLKO=spiflash_pads.clk, i_USRCCLKTS=0, i_USRDONEO=1,
                i_USRDONETS=1
            )
            spiflash_dummy = {
                "spiflash_1x": 9,
                "spiflash_4x": 11,
            }
            self.submodules.spiflash = spi_flash.SpiFlash(
                spiflash_pads,
                dummy=spiflash_dummy[kwargs["spiflash"]],
                div=2
            )
            self.add_constant("SPIFLASH_PAGE_SIZE", 256)
            self.add_constant("SPIFLASH_SECTOR_SIZE", 0x10000)
            self.add_wb_slave(
                mem_decoder(self.mem_map["spiflash"]),
                self.spiflash.bus
            )
            self.add_memory_region(
                "spiflash",
                self.mem_map["spiflash"] | self.shadow_base,
                16 * 1024 * 1024
            )


def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on CmodA7")
    builder_args(parser)
    BaseSoC.basesoc_args(parser)
    parser.set_defaults(
        no_compile_gateware=True,
        integrated_rom_size=0x8000,
        integrated_main_ram_size=0x8000,
        # integrated_sram_size=0,   # Litex will complain if 0!
        cpu_type="picorv32"
    )
    args = parser.parse_args()
    soc = BaseSoC(**vars(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()


if __name__ == "__main__":
    main()
