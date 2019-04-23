# This file is Copyright (c) 2019 Michael Betz <michibetz@gmail.com>
# License: BSD

from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform, iMPACT

_io = [
    ("user_led", 0, Pins("D17"), IOStandard("LVCMOS25")),
    ("user_led", 1, Pins("AB4"), IOStandard("LVCMOS25")),
    ("user_led", 2, Pins("D21"), IOStandard("LVCMOS25")),
    ("user_led", 3, Pins("W15"), IOStandard("LVCMOS25")),

    ("user_btn", 0, Pins("F3"), IOStandard("LVCMOS25")),
    ("user_btn", 1, Pins("G6"), IOStandard("LVCMOS25")),
    ("user_btn", 2, Pins("F5"), IOStandard("LVCMOS25")),
    ("user_btn", 3, Pins("C1"), IOStandard("LVCMOS25")),

    ("cpu_reset", 0, Pins("H8"), IOStandard("LVCMOS25")),

    ("serial", 0,
        Subsignal("cts", Pins("F19")),
        Subsignal("rts", Pins("F18")),
        Subsignal("tx", Pins("B21")),
        Subsignal("rx", Pins("H17")),
        IOStandard("LVCMOS25")
    ),

    ("clk200", 0,
        Subsignal("p", Pins("K21")),
        Subsignal("n", Pins("K22")),
        IOStandard("LVDS_25")
    ),

    ("eth_clocks", 0,
        # Subsignal("tx", Pins("L20")),  # Comment to force GMII 1G only mode
        Subsignal("gtx", Pins("AB7")),
        Subsignal("rx", Pins("P20")),
        IOStandard("LVCMOS25")
    ),
    ("eth", 0,
        Subsignal("rst_n", Pins("J22")),
        Subsignal("int_n", Pins("J20")),
        Subsignal("mdio", Pins("V20")),
        Subsignal("mdc", Pins("R19")),
        Subsignal("rx_dv", Pins("T22")),
        Subsignal("rx_er", Pins("U20")),
        Subsignal("rx_data", Pins("P19 Y22 Y21 W22 W20 V22 V21 U22")),
        Subsignal("tx_en", Pins("T8")),
        Subsignal("tx_er", Pins("U8")),
        Subsignal("tx_data", Pins("U10 T10 AB8 AA8 AB9 Y9 Y12 W12")),
        Subsignal("col", Pins("M16")),
        Subsignal("crs", Pins("N15")),
        IOStandard("LVCMOS25")
    ),
]

_connectors = [
    ("LPC", {
        "DP0_C2M_P": "B16",
        "DP0_C2M_N": "A16",
        "DP0_M2C_P": "D15",
        "DP0_M2C_N": "C15",
        "LA06_P": "D4",
        "LA06_N": "D5",
        "LA10_P": "H10",
        "LA10_N": "H11",
        "LA14_P": "C17",
        "LA14_N": "A17",
        "LA18_CC_P": "T12",
        "LA18_CC_N": "U12",
        "LA27_P": "AA10",
        "LA27_N": "AB10",
        "IIC_SCL_MAIN": "T21",
        "IIC_SDA_MAIN": "R22",
        "CLK1_M2C_P": "E16",
        "CLK1_M2C_N": "F16",
        "LA00_CC_P": "G9",
        "LA00_CC_N": "F10",
        "LA03_P": "B18",
        "LA03_N": "A18",
        "LA08_P": "B20",
        "LA08_N": "A20",
        "LA12_P": "H13",
        "LA12_N": "G13",
        "LA16_P": "C5",
        "LA16_N": "A5",
        "GBTCLK0_M2C_P": "E12",
        "GBTCLK0_M2C_N": "F12",
        "LA01_CC_P": "F14",
        "LA01_CC_N": "F15",
        "LA05_P": "C4",
        "LA05_N": "A4",
        "LA09_P": "F7",
        "LA09_N": "F8",
        "LA13_P": "G16",
        "LA13_N": "F17",
        "LA17_CC_P": "Y11",
        "LA17_CC_N": "AB11",
        "LA23_P": "U9",
        "LA23_N": "V9",
        "LA26_P": "U14",
        "LA26_N": "U13",
        "PRSNT_M2C_L": "Y16",
        "CLK0_M2C_P": "H12",
        "CLK0_M2C_N": "G11",
        "LA02_P": "G8",
        "LA02_N": "F9",
        "LA04_P": "C19",
        "LA04_N": "A19",
        "LA07_P": "B2",
        "LA07_N": "A2",
        "LA11_P": "H14",
        "LA11_N": "G15",
        "LA15_P": "D18",
        "LA20_P": "R9",
        "LA20_N": "R8",
        "LA22_P": "V7",
        "LA22_N": "W8",
        "LA25_P": "W14",
        "LA25_N": "Y14",
        "LA29_P": "T15",
        "LA29_N": "U15",
        "LA31_P": "U16",
        "LA31_N": "V15",
        "LA33_P": "Y17",
        "LA33_N": "AB17",
        "LA32_N": "Y18",
        "LA15_N": "D19",
        "LA19_P": "R11",
        "LA19_N": "T11",
        "LA21_P": "V11",
        "LA21_N": "W11",
        "LA24_P": "AA14",
        "LA24_N": "AB14",
        "LA28_P": "AA16",
        "LA28_N": "AB16",
        "LA30_P": "Y15",
        "LA30_N": "AB15",
        "LA32_P": "W17"
    }),
    ("SMA_GPIO", {
        "P": "B3",
        "N": "A3"
    }),
    ("SMA_USER_CLK", {
        "P": "M20",
        "N": "M19"
    }),
    ("SMA_MGT_CLK", {
        "P": "C11",
        "N": "D11"
    }),
]

class Platform(XilinxPlatform):
    default_clk_name = "clk200"
    default_clk_period = 5.0

    def __init__(self):
        XilinxPlatform.__init__(self, "xc6slx45t-fgg484-3", _io, _connectors, toolchain="ise")

    def create_programmer(self):
        return iMPACT()
