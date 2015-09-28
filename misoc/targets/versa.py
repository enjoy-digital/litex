from migen import *
from migen.genlib.io import CRG

from misoc.integration.soc_core import SoCCore


class BaseSoC(SoCCore):
    default_platform = "versa"
    def __init__(self, platform, **kwargs):
        SoCCore.__init__(self, platform,
                     clk_freq=100*1000000,
                     integrated_rom_size=0x8000,
                     **kwargs)
        self.submodules.crg = CRG(platform.request("clk100"), ~platform.request("rst_n"))
        self.comb += platform.request("user_led", 0).eq(ResetSignal())

default_subtarget = BaseSoC
