from migen.build.generic_platform import *
from migen.build.xilinx import XilinxPlatform


# Bank 34 and 35 voltage depend on J18 jumper setting
_io = [
        ("clk100", 0, Pins("Y9"), IOStandard("LVCMOS33")),

        ("user_btn", 0, Pins("P16"), IOStandard("LVCMOS18")),  # center
        ("user_btn", 1, Pins("R16"), IOStandard("LVCMOS18")),  # down
        ("user_btn", 2, Pins("N15"), IOStandard("LVCMOS18")),  # left
        ("user_btn", 3, Pins("R18"), IOStandard("LVCMOS18")),  # right
        ("user_btn", 4, Pins("T18"), IOStandard("LVCMOS18")),  # up

        ("user_sw", 0, Pins("F22"), IOStandard("LVCMOS18")),
        ("user_sw", 1, Pins("G22"), IOStandard("LVCMOS18")),
        ("user_sw", 2, Pins("H22"), IOStandard("LVCMOS18")),
        ("user_sw", 3, Pins("F21"), IOStandard("LVCMOS18")),
        ("user_sw", 4, Pins("H19"), IOStandard("LVCMOS18")),
        ("user_sw", 5, Pins("H18"), IOStandard("LVCMOS18")),
        ("user_sw", 6, Pins("H17"), IOStandard("LVCMOS18")),
        ("user_sw", 7, Pins("M15"), IOStandard("LVCMOS18")),

        ("user_led", 0, Pins("T22"), IOStandard("LVCMOS33")),
        ("user_led", 1, Pins("T21"), IOStandard("LVCMOS33")),
        ("user_led", 2, Pins("U22"), IOStandard("LVCMOS33")),
        ("user_led", 3, Pins("U21"), IOStandard("LVCMOS33")),
        ("user_led", 4, Pins("V22"), IOStandard("LVCMOS33")),
        ("user_led", 5, Pins("W22"), IOStandard("LVCMOS33")),
        ("user_led", 6, Pins("U19"), IOStandard("LVCMOS33")),
        ("user_led", 7, Pins("U14"), IOStandard("LVCMOS33")),

        # A
        ("pmod", 0, Pins("Y11 AA11 Y10 AA9 AB11 AB10 AB9 AA8"),
            IOStandard("LVCMOS33")),
        # B
        ("pmod", 1, Pins("W12 W11 V10 W8 V12 W10 V9 V8"),
            IOStandard("LVCMOS33")),
        # C
        ("pmod", 2,
            Subsignal("n", Pins("AB6 AA4 T6 U4")),
            Subsignal("p", Pins("AB7 Y4 R6 T4")),
            IOStandard("LVCMOS33")),
        # D
        ("pmod", 3,
            Subsignal("n", Pins("W7 V4 W5 U5")),
            Subsignal("p", Pins("V7 V5 W6 U6")),
            IOStandard("LVCMOS33")),

        ("audio", 0,
            Subsignal("adr", Pins("AB1 Y5")),
            Subsignal("gpio", Pins("Y8 AA7 AA6 Y6")),
            Subsignal("mclk", Pins("AB2")),
            Subsignal("sck", Pins("AB4")),
            Subsignal("sda", Pins("AB5")),
            IOStandard("LVCMOS33")),

        ("oled", 0,
            Subsignal("dc", Pins("U10")),
            Subsignal("res", Pins("U9")),
            Subsignal("sclk", Pins("AB12")),
            Subsignal("sdin", Pins("AA12")),
            Subsignal("vbat", Pins("U11")),
            Subsignal("vdd", Pins("U12")),
            IOStandard("LVCMOS33")),

        ("hdmi", 0,
            Subsignal("clk", Pins("W18")),
            Subsignal("d", Pins(
                "Y13 AA13 AA14 Y14 AB15 AB16 AA16 AB17 "
                "AA17 Y15 W13 W15 V15 U17 V14 V13")),
            Subsignal("de", Pins("U16")),
            Subsignal("hsync", Pins("V17")),
            Subsignal("vsync", Pins("W17")),
            Subsignal("int", Pins("W16")),
            Subsignal("scl", Pins("AA18")),
            Subsignal("sda", Pins("Y16")),
            Subsignal("spdif", Pins("U15")),
            Subsignal("spdifo", Pins("Y18")),
            IOStandard("LVCMOS33")),

        ("netic16", 0,
            Subsignal("w20", Pins("W20")),
            Subsignal("w21", Pins("W21")),
            IOStandard("LVCMOS33")),

        ("vga", 0,
            Subsignal("r", Pins("V20 U20 V19 V18")),
            Subsignal("g", Pins("AB22 AA22 AB21 AA21")),
            Subsignal("b", Pins("Y21 Y20 AB20 AB19")),
            Subsignal("hsync_n", Pins("AA19")),
            Subsignal("vsync_n", Pins("Y19")),
            IOStandard("LVCMOS33")),

        ("usb_otg", 0,
            Subsignal("vbusoc", Pins("L16")),
            Subsignal("reset_n", Pins("G17")),
            IOStandard("LVCMOS18")),

        ("pudc_b", 0, Pins("K16"), IOStandard("LVCMOS18")),

        ("xadc", 0,
            Subsignal("gio", Pins("H15 R15 K15 J15")),
            Subsignal("ad0_n", Pins("E16")),
            Subsignal("ad0_p", Pins("F16")),
            Subsignal("ad8_n", Pins("D17")),
            Subsignal("ad8_p", Pins("D16")),
            IOStandard("LVCMOS18")),

        ("fmc_clocks", 0,
            Subsignal("clk0_n", Pins("L19")),
            Subsignal("clk0_p", Pins("L18")),
            Subsignal("clk1_n", Pins("C19")),
            Subsignal("clk1_p", Pins("D18")),
            IOStandard("LVCMOS18")),

        ("fmc", 0,
            Subsignal("scl", Pins("R7")),
            Subsignal("sda", Pins("U7")),

            Subsignal("prsnt", Pins("AB14")),

            # 0, 1, 17, 18 can be clock signals
            Subsignal("la_n", Pins(
                "M20 N20 P18 P22 M22 K18 L22 T17 "
                "J22 R21 T19 N18 P21 M17 K20 J17 "
                "K21 B20 C20 G16 G21 E20 F19 D15 "
                "A19 C22 E18 D21 A17 C18 B15 B17 "
                "A22 B22")),
            Subsignal("la_p", Pins(
                "M19 N19 P17 N22 M21 J18 L21 T16 "
                "J21 R20 R19 N17 P20 L17 K19 J16 "
                "J20 B19 D20 G15 G20 E19 G19 E15 "
                "A18 D22 F18 E21 A16 C17 C15 B16 "
                "A21 B21")),
            IOStandard("LVCMOS18")),
]


class Platform(XilinxPlatform):
    default_clk_name = "clk100"
    default_clk_period = 10

    def __init__(self):
        XilinxPlatform.__init__(self, "xc7z020-clg484-1", _io)
