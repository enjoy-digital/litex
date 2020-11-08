#
# This file is part of LiteX.
#
# Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2015 Yann Sionneau <ys@m-labs.hk>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform
from litex.build.openocd import OpenOCD

# IOs ----------------------------------------------------------------------------------------------

_io = [
    # Clk / Rst
    ("clk200", 0,
        Subsignal("p", Pins("AD12"), IOStandard("LVDS")),
        Subsignal("n", Pins("AD11"), IOStandard("LVDS"))
    ),

    ("clk156", 0,
        Subsignal("p", Pins("K28"), IOStandard("LVDS_25")),
        Subsignal("n", Pins("K29"), IOStandard("LVDS_25"))
    ),
    ("cpu_reset", 0, Pins("AB7"), IOStandard("LVCMOS15")),

    # Leds
    ("user_led", 0, Pins("AB8"),  IOStandard("LVCMOS15")),
    ("user_led", 1, Pins("AA8"),  IOStandard("LVCMOS15")),
    ("user_led", 2, Pins("AC9"),  IOStandard("LVCMOS15")),
    ("user_led", 3, Pins("AB9"),  IOStandard("LVCMOS15")),
    ("user_led", 4, Pins("AE26"), IOStandard("LVCMOS25")),
    ("user_led", 5, Pins("G19"),  IOStandard("LVCMOS25")),
    ("user_led", 6, Pins("E18"),  IOStandard("LVCMOS25")),
    ("user_led", 7, Pins("F16"),  IOStandard("LVCMOS25")),

    # Buttons
    ("user_btn_c", 0, Pins("G12"),  IOStandard("LVCMOS25")),
    ("user_btn_n", 0, Pins("AA12"), IOStandard("LVCMOS15")),
    ("user_btn_s", 0, Pins("AB12"), IOStandard("LVCMOS15")),
    ("user_btn_w", 0, Pins("AC6"),  IOStandard("LVCMOS15")),
    ("user_btn_e", 0, Pins("AG5"),  IOStandard("LVCMOS15")),

    # Switches
    ("user_dip_btn", 0, Pins("Y29"),  IOStandard("LVCMOS25")),
    ("user_dip_btn", 1, Pins("W29"),  IOStandard("LVCMOS25")),
    ("user_dip_btn", 2, Pins("AA28"), IOStandard("LVCMOS25")),
    ("user_dip_btn", 3, Pins("Y28"),  IOStandard("LVCMOS25")),

    # SMA
    ("user_sma_clock", 0,
        Subsignal("p", Pins("L25"), IOStandard("LVDS_25"),
            Misc("DIFF_TERM=TRUE")),
        Subsignal("n", Pins("K25"), IOStandard("LVDS_25"),
            Misc("DIFF_TERM=TRUE"))
    ),
    ("user_sma_clock_p", 0, Pins("L25"), IOStandard("LVCMOS25")),
    ("user_sma_clock_n", 0, Pins("K25"), IOStandard("LVCMOS25")),
    ("user_sma_gpio_p", 0, Pins("Y23"), IOStandard("LVCMOS25")),
    ("user_sma_gpio_n", 0, Pins("Y24"), IOStandard("LVCMOS25")),

    # I2C
    ("i2c", 0,
        Subsignal("scl", Pins("K21")),
        Subsignal("sda", Pins("L21")),
        IOStandard("LVCMOS25")),

    # Serial
    ("serial", 0,
        Subsignal("cts", Pins("L27")),
        Subsignal("rts", Pins("K23")),
        Subsignal("tx",  Pins("K24")),
        Subsignal("rx",  Pins("M19")),
        IOStandard("LVCMOS25")
    ),

    # DDR3 SDRAM
    ("ddram", 0,
        Subsignal("a",       Pins(
            "AH12 AG13 AG12 AF12 AJ12 AJ13 AJ14 AH14",
            "AK13 AK14 AF13 AE13 AJ11 AH11 AK10 AK11"),
            IOStandard("SSTL15")),
        Subsignal("ba",      Pins("AH9 AG9 AK9"), IOStandard("SSTL15")),
        Subsignal("ras_n",   Pins("AD9"),  IOStandard("SSTL15")),
        Subsignal("cas_n",   Pins("AC11"), IOStandard("SSTL15")),
        Subsignal("we_n",    Pins("AE9"),  IOStandard("SSTL15")),
        Subsignal("cs_n",    Pins("AC12"), IOStandard("SSTL15")),
        Subsignal("dm",      Pins(
            "Y16 AB17 AF17 AE16 AK5 AJ3 AF6 AC7"),
            IOStandard("SSTL15")),
        Subsignal("dq",      Pins(
            "AA15 AA16 AC14 AD14 AA17 AB15 AE15 Y15",
            "AB19 AD16 AC19 AD17 AA18 AB18 AE18 AD18",
            "AG19 AK19 AG18 AF18 AH19 AJ19 AE19 AD19",
            "AK16 AJ17 AG15 AF15 AH17 AG14 AH15 AK15",
            "AK8 AK6 AG7 AF7 AF8 AK4 AJ8 AJ6",
            "AH5 AH6 AJ2 AH2 AH4 AJ4 AK1 AJ1",
            "AF1 AF2 AE4 AE3 AF3 AF5 AE1 AE5",
            "AC1 AD3 AC4 AC5 AE6 AD6 AC2 AD4"),
            IOStandard("SSTL15_T_DCI")),
        Subsignal("dqs_p",   Pins("AC16 Y19 AJ18 AH16 AH7 AG2 AG4 AD2"),
            IOStandard("DIFF_SSTL15")),
        Subsignal("dqs_n",   Pins("AC15 Y18 AK18 AJ16 AJ7 AH1 AG3 AD1"),
            IOStandard("DIFF_SSTL15")),
        Subsignal("clk_p",   Pins("AG10"), IOStandard("DIFF_SSTL15")),
        Subsignal("clk_n",   Pins("AH10"), IOStandard("DIFF_SSTL15")),
        Subsignal("cke",     Pins("AF10"), IOStandard("SSTL15")),
        Subsignal("odt",     Pins("AD8"),  IOStandard("SSTL15")),
        Subsignal("reset_n", Pins("AK3"),  IOStandard("LVCMOS15")),
        Misc("SLEW=FAST"),
        Misc("VCCAUX_IO=HIGH")
    ),

    # SPIFlash
    ("spiflash", 0,  # clock needs to be accessed through STARTUPE2
        Subsignal("cs_n", Pins("U19")),
        Subsignal("dq",   Pins("P24", "R25", "R20", "R21")),
        IOStandard("LVCMOS25")
    ),

    # SDCard
    ("spisdcard", 0,
        Subsignal("clk",  Pins("AB23")),
        Subsignal("cs_n", Pins("AC21")),
        Subsignal("mosi", Pins("AB22"), Misc("PULLUP")),
        Subsignal("miso", Pins("AC20"), Misc("PULLUP")),
        Misc("SLEW=FAST"),
        IOStandard("LVCMOS25")
    ),
    ("sdcard", 0,
        Subsignal("clk", Pins("AB23")),
        Subsignal("cmd", Pins("AB22"), Misc("PULLUP True")),
        Subsignal("data", Pins("AC20 AA23 AA22 AC21"), Misc("PULLUP True")),
        Misc("SLEW=FAST"),
        IOStandard("LVCMOS25")
    ),

    # GMII Ethernet
    ("eth_clocks", 0,
        Subsignal("tx",  Pins("M28")),
        Subsignal("gtx", Pins("K30")),
        Subsignal("rx",  Pins("U27")),
        IOStandard("LVCMOS25")
    ),
    ("eth", 0,
        Subsignal("rst_n",   Pins("L20")),
        Subsignal("int_n",   Pins("N30")),
        Subsignal("mdio",    Pins("J21")),
        Subsignal("mdc",     Pins("R23")),
        Subsignal("rx_dv",   Pins("R28")),
        Subsignal("rx_er",   Pins("V26")),
        Subsignal("rx_data", Pins("U30 U25 T25 U28 R19 T27 T26 T28")),
        Subsignal("tx_en",   Pins("M27")),
        Subsignal("tx_er",   Pins("N29")),
        Subsignal("tx_data", Pins("N27 N25 M29 L28 J26 K26 L30 J28")),
        Subsignal("col",     Pins("W19")),
        Subsignal("crs",     Pins("R30")),
        IOStandard("LVCMOS25")
    ),

    # LCD
    ("lcd", 0,
        Subsignal("db", Pins("AA13 AA10 AA11 Y10")),
        Subsignal("e",  Pins("AB10")),
        Subsignal("rs", Pins("Y11")),
        Subsignal("rw", Pins("AB13")),
        IOStandard("LVCMOS15")
    ),

    # Rotary Encoder
    ("rotary", 0,
        Subsignal("a", Pins("Y26")),
        Subsignal("b", Pins("Y25")),
        Subsignal("push", Pins("AA26")),
        IOStandard("LVCMOS25")
    ),

    # HDMI
    ("hdmi", 0,
        Subsignal("d", Pins(
            "B23 A23 E23 D23 F25 E25 E24 D24",
            "F26 E26 G23 G24 J19 H19 L17 L18",
            "K19 K20")),
        Subsignal("de",        Pins("H17")),
        Subsignal("clk",       Pins("K18")),
        Subsignal("vsync",     Pins("H20")),
        Subsignal("hsync",     Pins("J18")),
        Subsignal("int",       Pins("AH24")),
        Subsignal("spdif",     Pins("J17")),
        Subsignal("spdif_out", Pins("G20")),
        IOStandard("LVCMOS25")
    ),

    # PCIe
    ("pcie_x1", 0,
        Subsignal("rst_n", Pins("G25"), IOStandard("LVCMOS25")),
        Subsignal("clk_p", Pins("U8")),
        Subsignal("clk_n", Pins("U7")),
        Subsignal("rx_p",  Pins("M6")),
        Subsignal("rx_n",  Pins("M5")),
        Subsignal("tx_p",  Pins("L4")),
        Subsignal("tx_n",  Pins("L3"))
    ),
    ("pcie_x2", 0,
        Subsignal("rst_n", Pins("G25"), IOStandard("LVCMOS25")),
        Subsignal("clk_p", Pins("U8")),
        Subsignal("clk_n", Pins("U7")),
        Subsignal("rx_p",  Pins("M6 P6")),
        Subsignal("rx_n",  Pins("M5 P5")),
        Subsignal("tx_p",  Pins("L4 M2")),
        Subsignal("tx_n",  Pins("L3 M1"))
    ),
    ("pcie_x4", 0,
        Subsignal("rst_n", Pins("G25"), IOStandard("LVCMOS25")),
        Subsignal("clk_p", Pins("U8")),
        Subsignal("clk_n", Pins("U7")),
        Subsignal("rx_p",  Pins("M6 P6 R4 T6")),
        Subsignal("rx_n",  Pins("M5 P5 R3 T5")),
        Subsignal("tx_p",  Pins("L4 M2 N4 P2")),
        Subsignal("tx_n",  Pins("L3 M1 N3 P1"))
    ),
    ("pcie_x8", 0,
        Subsignal("rst_n", Pins("G25"), IOStandard("LVCMOS25")),
        Subsignal("clk_p", Pins("U8")),
        Subsignal("clk_n", Pins("U7")),
        Subsignal("rx_p",  Pins("M6 P6 R4 T6 V6 W4 Y6 AA4")),
        Subsignal("rx_n",  Pins("M5 P5 R3 T5 V5 W3 Y5 AA3")),
        Subsignal("tx_p",  Pins("L4 M2 N4 P2 T2 U4 V2 Y2")),
        Subsignal("tx_n",  Pins("L3 M1 N3 P1 T1 U3 V1 Y1"))
    ),

    # SGMII Clk
    ("sgmii_clock", 0,
        Subsignal("p", Pins("G8")),
        Subsignal("n", Pins("G7"))
    ),

    # SMA
    ("user_sma_mgt_refclk", 0,
        Subsignal("p", Pins("J8")),
        Subsignal("n", Pins("J7"))
    ),
    ("user_sma_mgt_tx", 0,
        Subsignal("p", Pins("K2")),
        Subsignal("n", Pins("K1"))
    ),
    ("user_sma_mgt_rx", 0,
        Subsignal("p", Pins("K6")),
        Subsignal("n", Pins("K5"))
    ),

    # SFP
    ("sfp", 0,  # inverted prior to HW rev 1.1
        Subsignal("txp", Pins("H2")),
        Subsignal("txn", Pins("H1")),
        Subsignal("rxp", Pins("G4")),
        Subsignal("rxn", Pins("G3")),
    ),
    ("sfp_tx", 0,  # inverted prior to HW rev 1.1
        Subsignal("p", Pins("H2")),
        Subsignal("n", Pins("H1"))
    ),
    ("sfp_rx", 0,  # inverted prior to HW rev 1.1
        Subsignal("p", Pins("G4")),
        Subsignal("n", Pins("G3"))
    ),
    ("sfp_tx_disable_n", 0, Pins("Y20"), IOStandard("LVCMOS25")),
    ("sfp_rx_los",       0, Pins("P19"), IOStandard("LVCMOS25")),

    # SI5324
    ("si5324", 0,
        Subsignal("rst_n", Pins("AE20"), IOStandard("LVCMOS25")),
        Subsignal("int",   Pins("AG24"), IOStandard("LVCMOS25"))
    ),
    ("si5324_clkin", 0,
        Subsignal("p", Pins("W27"), IOStandard("LVDS_25")),
        Subsignal("n", Pins("W28"), IOStandard("LVDS_25"))
    ),
    ("si5324_clkout", 0,
        Subsignal("p", Pins("L8")),
        Subsignal("n", Pins("L7"))
    ),

    # Others
    ("vadj_on_b", 0, Pins("J27"), IOStandard("LVCMOS25")),
]

# Connectors ---------------------------------------------------------------------------------------

_connectors = [
    ("HPC", {
        "DP1_M2C_P"     : "D6",
        "DP1_M2C_N"     : "D5",
        "DP2_M2C_P"     : "B6",
        "DP2_M2C_N"     : "B5",
        "DP3_M2C_P"     : "A8",
        "DP3_M2C_N"     : "A7",
        "DP1_C2M_P"     : "C4",
        "DP1_C2M_N"     : "C3",
        "DP2_C2M_P"     : "B2",
        "DP2_C2M_N"     : "B1",
        "DP3_C2M_P"     : "A4",
        "DP3_C2M_N"     : "A3",
        "DP0_C2M_P"     : "D2",
        "DP0_C2M_N"     : "D1",
        "DP0_M2C_P"     : "E4",
        "DP0_M2C_N"     : "E3",
        "LA06_P"        : "H30",
        "LA06_N"        : "G30",
        "LA10_P"        : "D29",
        "LA10_N"        : "C30",
        "LA14_P"        : "B28",
        "LA14_N"        : "A28",
        "LA18_CC_P"     : "F21",
        "LA18_CC_N"     : "E21",
        "LA27_P"        : "C19",
        "LA27_N"        : "B19",
        "HA01_CC_P"     : "H14",
        "HA01_CC_N"     : "G14",
        "HA05_P"        : "F15",
        "HA05_N"        : "E16",
        "HA09_P"        : "F12",
        "HA09_N"        : "E13",
        "HA13_P"        : "L16",
        "HA13_N"        : "K16",
        "HA16_P"        : "L15",
        "HA16_N"        : "K15",
        "HA20_P"        : "K13",
        "HA20_N"        : "J13",
        "CLK1_M2C_P"    : "D17",
        "CLK1_M2C_N"    : "D18",
        "LA00_CC_P"     : "C25",
        "LA00_CC_N"     : "B25",
        "LA03_P"        : "H26",
        "LA03_N"        : "H27",
        "LA08_P"        : "E29",
        "LA08_N"        : "E30",
        "LA12_P"        : "C29",
        "LA12_N"        : "B29",
        "LA16_P"        : "B27",
        "LA16_N"        : "A27",
        "LA20_P"        : "E19",
        "LA20_N"        : "D19",
        "LA22_P"        : "C20",
        "LA22_N"        : "B20",
        "LA25_P"        : "G17",
        "LA25_N"        : "F17",
        "LA29_P"        : "C17",
        "LA29_N"        : "B17",
        "LA31_P"        : "G22",
        "LA31_N"        : "F22",
        "LA33_P"        : "H21",
        "LA33_N"        : "H22",
        "HA03_P"        : "C12",
        "HA03_N"        : "B12",
        "HA07_P"        : "B14",
        "HA07_N"        : "A15",
        "HA11_P"        : "B13",
        "HA11_N"        : "A13",
        "HA14_P"        : "J16",
        "HA14_N"        : "H16",
        "HA18_P"        : "K14",
        "HA18_N"        : "J14",
        "HA22_P"        : "L11",
        "HA22_N"        : "K11",
        "GBTCLK1_M2C_P" : "E8",
        "GBTCLK1_M2C_N" : "E7",
        "GBTCLK0_M2C_P" : "C8",
        "GBTCLK0_M2C_N" : "C7",
        "LA01_CC_P"     : "D26",
        "LA01_CC_N"     : "C26",
        "LA05_P"        : "G29",
        "LA05_N"        : "F30",
        "LA09_P"        : "B30",
        "LA09_N"        : "A30",
        "LA13_P"        : "A25",
        "LA13_N"        : "A26",
        "LA17_CC_P"     : "F20",
        "LA17_CC_N"     : "E20",
        "LA23_P"        : "B22",
        "LA23_N"        : "A22",
        "LA26_P"        : "B18",
        "LA26_N"        : "A18",
        "PG_M2C"        : "J29",
        "HA00_CC_P"     : "D12",
        "HA00_CC_N"     : "D13",
        "HA04_P"        : "F11",
        "HA04_N"        : "E11",
        "HA08_P"        : "E14",
        "HA08_N"        : "E15",
        "HA12_P"        : "C15",
        "HA12_N"        : "B15",
        "HA15_P"        : "H15",
        "HA15_N"        : "G15",
        "HA19_P"        : "H11",
        "HA19_N"        : "H12",
        "PRSNT_M2C_B"   : "M20",
        "CLK0_M2C_P"    : "D27",
        "CLK0_M2C_N"    : "C27",
        "LA02_P"        : "H24",
        "LA02_N"        : "H25",
        "LA04_P"        : "G28",
        "LA04_N"        : "F28",
        "LA07_P"        : "E28",
        "LA07_N"        : "D28",
        "LA11_P"        : "G27",
        "LA11_N"        : "F27",
        "LA15_P"        : "C24",
        "LA15_N"        : "B24",
        "LA19_P"        : "G18",
        "LA19_N"        : "F18",
        "LA21_P"        : "A20",
        "LA21_N"        : "A21",
        "LA24_P"        : "A16",
        "LA24_N"        : "A17",
        "LA28_P"        : "D16",
        "LA28_N"        : "C16",
        "LA30_P"        : "D22",
        "LA30_N"        : "C22",
        "LA32_P"        : "D21",
        "LA32_N"        : "C21",
        "HA02_P"        : "D11",
        "HA02_N"        : "C11",
        "HA06_P"        : "D14",
        "HA06_N"        : "C14",
        "HA10_P"        : "A11",
        "HA10_N"        : "A12",
        "HA17_CC_P"     : "G13",
        "HA17_CC_N"     : "F13",
        "HA21_P"        : "J11",
        "HA21_N"        : "J12",
        "HA23_P"        : "L12",
        "HA23_N"        : "L13",
        }
    ),
    ("LPC", {
        "GBTCLK0_M2C_P" : "N8",
        "GBTCLK0_M2C_N" : "N7",
        "DP0_C2M_P"     : "F2",
        "DP0_C2M_N"     : "F1",
        "DP0_M2C_P"     : "F6",
        "DP0_M2C_N"     : "F5",
        "LA01_CC_P"     : "AE23",
        "LA01_CC_N"     : "AF23",
        "LA05_P"        : "AG22",
        "LA05_N"        : "AH22",
        "LA09_P"        : "AK23",
        "LA09_N"        : "AK24",
        "LA13_P"        : "AB24",
        "LA13_N"        : "AC25",
        "LA17_CC_P"     : "AB27",
        "LA17_CC_N"     : "AC27",
        "LA23_P"        : "AH26",
        "LA23_N"        : "AH27",
        "LA26_P"        : "AK29",
        "LA26_N"        : "AK30",
        "CLK0_M2C_P"    : "AF22",
        "CLK0_M2C_N"    : "AG23",
        "LA02_P"        : "AF20",
        "LA02_N"        : "AF21",
        "LA04_P"        : "AH21",
        "LA04_N"        : "AJ21",
        "LA07_P"        : "AG25",
        "LA07_N"        : "AH25",
        "LA11_P"        : "AE25",
        "LA11_N"        : "AF25",
        "LA15_P"        : "AC24",
        "LA15_N"        : "AD24",
        "LA19_P"        : "AJ26",
        "LA19_N"        : "AK26",
        "LA21_P"        : "AG27",
        "LA21_N"        : "AG28",
        "LA24_P"        : "AG30",
        "LA24_N"        : "AH30",
        "LA28_P"        : "AE30",
        "LA28_N"        : "AF30",
        "LA30_P"        : "AB29",
        "LA30_N"        : "AB30",
        "LA32_P"        : "Y30",
        "LA32_N"        : "AA30",
        "LA06_P"        : "AK20",
        "LA06_N"        : "AK21",
        "LA10_P"        : "AJ24",
        "LA10_N"        : "AK25",
        "LA14_P"        : "AD21",
        "LA14_N"        : "AE21",
        "LA18_CC_P"     : "AD27",
        "LA18_CC_N"     : "AD28",
        "LA27_P"        : "AJ28",
        "LA27_N"        : "AJ29",
        "CLK1_M2C_P"    : "AG29",
        "CLK1_M2C_N"    : "AH29",
        "LA00_CC_P"     : "AD23",
        "LA00_CC_N"     : "AE24",
        "LA03_P"        : "AG20",
        "LA03_N"        : "AH20",
        "LA08_P"        : "AJ22",
        "LA08_N"        : "AJ23",
        "LA12_P"        : "AA20",
        "LA12_N"        : "AB20",
        "LA16_P"        : "AC22",
        "LA16_N"        : "AD22",
        "LA20_P"        : "AF26",
        "LA20_N"        : "AF27",
        "LA22_P"        : "AJ27",
        "LA22_N"        : "AK28",
        "LA25_P"        : "AC26",
        "LA25_N"        : "AD26",
        "LA29_P"        : "AE28",
        "LA29_N"        : "AF28",
        "LA31_P"        : "AD29",
        "LA31_N"        : "AE29",
        "LA33_P"        : "AC29",
        "LA33_N"        : "AC30",
        }
    ),
    ("XADC", {
        "GPIO0"   : "AB25",
        "GPIO1"   : "AA25",
        "GPIO2"   : "AB28",
        "GPIO3"   : "AA27",
        "VAUX0_N" : "J24",
        "VAUX0_P" : "J23",
        "VAUX8_N" : "L23",
        "VAUX8_P" : "L22",
        }
    ),
]

# Platform -----------------------------------------------------------------------------------------

class Platform(XilinxPlatform):
    default_clk_name   = "clk156"
    default_clk_period = 1e9/156.5e6

    def __init__(self):
        XilinxPlatform.__init__(self, "xc7k325t-ffg900-2", _io, _connectors, toolchain="vivado")
        self.add_platform_command("""
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 2.5 [current_design]
""")
        self.toolchain.bitstream_commands = ["set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]"]
        self.toolchain.additional_commands = ["write_cfgmem -force -format bin -interface spix4 -size 16 -loadbit \"up 0x0 {build_name}.bit\" -file {build_name}.bin"]

    def create_programmer(self):
        return OpenOCD("openocd_xc7_ft2232.cfg", "bscan_spi_xc7a325t.bit")

    def do_finalize(self, fragment):
        XilinxPlatform.do_finalize(self, fragment)
        self.add_period_constraint(self.lookup_request("clk200",        loose=True), 1e9/200e6)
        self.add_period_constraint(self.lookup_request("eth_clocks:rx", loose=True), 1e9/125e6)
        self.add_period_constraint(self.lookup_request("eth_clocks:tx", loose=True), 1e9/125e6)
        self.add_platform_command("set_property DCI_CASCADE {{32 34}} [get_iobanks 33]")
