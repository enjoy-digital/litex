from migen.build.generic_platform import *
from migen.build.xilinx import XilinxPlatform


_io = [
    # System clock (Differential 200MHz)
    ("clk200", 0,
        Subsignal("p", Pins("J9"), IOStandard("LVDS_25"), Misc("DIFF_TERM=TRUE")),
        Subsignal("n", Pins("H9"), IOStandard("LVDS_25"), Misc("DIFF_TERM=TRUE"))
    ),

    # User clock (66MHz)
    ("clk66", 0, Pins("U23"), IOStandard("LVCMOS25")),

    # CPU reset switch
    ("cpu_reset", 0, Pins("H10"), IOStandard("SSTL15")),

    # LEDs
    ("user_led", 0, Pins("AC22"), IOStandard("LVCMOS25"), Misc("SLEW=SLOW")),
    ("user_led", 1, Pins("AC24"), IOStandard("LVCMOS25"), Misc("SLEW=SLOW")),
    ("user_led", 2, Pins("AE22"), IOStandard("LVCMOS25"), Misc("SLEW=SLOW")),
    ("user_led", 3, Pins("AE23"), IOStandard("LVCMOS25"), Misc("SLEW=SLOW")),
    ("user_led", 4, Pins("AB23"), IOStandard("LVCMOS25"), Misc("SLEW=SLOW")),
    ("user_led", 5, Pins("AG23"), IOStandard("LVCMOS25"), Misc("SLEW=SLOW")),
    ("user_led", 6, Pins("AE24"), IOStandard("LVCMOS25"), Misc("SLEW=SLOW")),
    ("user_led", 7, Pins("AD24"), IOStandard("LVCMOS25"), Misc("SLEW=SLOW")),

    # USB-to-UART
    ("serial", 0,
        Subsignal("tx", Pins("J25"), IOStandard("LVCMOS25")),
        Subsignal("rx", Pins("J24"), IOStandard("LVCMOS25"))
    ),

    # 10/100/1000 Tri-Speed Ethernet PHY
    ("eth_clocks", 0,
        Subsignal("rx", Pins("AP11")),
        Subsignal("tx", Pins("AD12")),
        IOStandard("LVCMOS25")
    ),
    ("eth", 0,
        Subsignal("rst_n", Pins("AH13")),
        Subsignal("dv", Pins("AM13")),
        Subsignal("rx_er", Pins("AG12")),
        Subsignal("rx_data", Pins("AN13 AF14 AE14 AN12 AM12 AD11 AC12 AC13")),
        Subsignal("tx_en", Pins("AJ10")),
        Subsignal("tx_er", Pins("AH10")),
        Subsignal("tx_data", Pins("AM11 AL11 AG10 AG11 AL10 AM10 AE11 AF11")),
        Subsignal("col", Pins("AK13")),
        Subsignal("crs", Pins("AL13")),
        IOStandard("LVCMOS25")
    )
]


class Platform(XilinxPlatform):
    default_clk_name = "clk200"
    default_clk_period = 5

    def __init__(self):
        XilinxPlatform.__init__(self, "xc6vlx240t-ff1156-1", _io)
