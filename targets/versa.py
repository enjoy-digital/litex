from migen.fhdl.std import *
from migen.bus import wishbone
from migen.genlib.io import CRG

from misoc.soc import SoC


class BaseSoC(SoC):
    default_platform = "versa"
    def __init__(self, platform, **kwargs):
        SoC.__init__(self, platform,
                     clk_freq=100*1000000,
                     integrated_rom_size=0x8000,
                     **kwargs)
        self.submodules.crg = CRG(platform.request("clk100"), ~platform.request("rst_n"))
        self.comb += platform.request("user_led", 0).eq(ResetSignal())

default_subtarget = BaseSoC
