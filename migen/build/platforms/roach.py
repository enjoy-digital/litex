from migen.build.generic_platform import *
from migen.build.xilinx import XilinxPlatform


_io = [
    ("epb", 0,
        Subsignal("cs_n", Pins("K13")),
        Subsignal("r_w_n", Pins("AF20")),
        Subsignal("be_n", Pins("AF14 AF18")),
        Subsignal("oe_n", Pins("AF21")),
        Subsignal("addr", Pins("AE23 AE22 AG18 AG12 AG15 AG23 AF19 AE12 AG16 AF13 AG20 AF23",
            "AH17 AH15 L20 J22 H22 L15 L16 K22 K21 K16 J15")),
        Subsignal("addr_gp", Pins("L21 G22 K23 K14 L14 J12")),
        Subsignal("data", Pins("AF15 AE16 AE21 AD20 AF16 AE17 AE19 AD19 AG22 AH22 AH12 AG13",
            "AH20 AH19 AH14 AH13")),
        Subsignal("rdy", Pins("K12")),
        IOStandard("LVCMOS33")
    ),
    ("roach_clocks", 0,
        Subsignal("epb_clk", Pins("AH18"), IOStandard("LVCMOS33")),
        Subsignal("sys_clk_n", Pins("H13")),
        Subsignal("sys_clk_p", Pins("J14")),
        Subsignal("aux0_clk_p", Pins("G15")),
        Subsignal("aux0_clk_n", Pins("G16")),
        Subsignal("aux1_clk_p", Pins("H14")),
        Subsignal("aux1_clk_n", Pins("H15")),
        Subsignal("dly_clk_n", Pins("J17")),
        Subsignal("dly_clk_p", Pins("J16")),
    ),
]


class Platform(XilinxPlatform):
    def __init__(self):
        XilinxPlatform.__init__(self, "xc5vsx95t-ff1136-1", _io)
