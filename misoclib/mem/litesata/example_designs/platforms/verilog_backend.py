from mibuild.generic_platform import *
from mibuild.xilinx.platform import XilinxPlatform

_io = [
    ("sys_clk", 0, Pins("X")),
    ("sys_rst", 1, Pins("X")),
    ("sata_clocks", 0,
        Subsignal("refclk_p", Pins("X")),
        Subsignal("refclk_n", Pins("X")),
    ),
    ("sata", 0,
        Subsignal("txp", Pins("X")),
        Subsignal("txn", Pins("X")),
        Subsignal("rxp", Pins("X")),
        Subsignal("rxn", Pins("X")),
    ),
]


class Platform(XilinxPlatform):
    def __init__(self, device="xc7k325t", programmer=""):
        XilinxPlatform.__init__(self, device, _io)

    def do_finalize(self, *args, **kwargs):
        pass
