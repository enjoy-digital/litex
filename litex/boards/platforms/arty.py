# This file is Copyright (c) 2015 Yann Sionneau <yann.sionneau@gmail.com>
# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform
from litex.build.openocd import OpenOCD

# IOs ----------------------------------------------------------------------------------------------

_io = [
    ("user_led", 0, Pins("H5"),  IOStandard("LVCMOS33")),
    ("user_led", 1, Pins("J5"),  IOStandard("LVCMOS33")),
    ("user_led", 2, Pins("T9"),  IOStandard("LVCMOS33")),
    ("user_led", 3, Pins("T10"), IOStandard("LVCMOS33")),

    ("rgb_led", 0,
        Subsignal("r", Pins("G6")),
        Subsignal("g", Pins("F6")),
        Subsignal("b", Pins("E1")),
        IOStandard("LVCMOS33"),
    ),

    ("rgb_led", 1,
        Subsignal("r", Pins("G3")),
        Subsignal("g", Pins("J4")),
        Subsignal("b", Pins("G4")),
        IOStandard("LVCMOS33"),
    ),

    ("rgb_led", 2,
        Subsignal("r", Pins("J3")),
        Subsignal("g", Pins("J2")),
        Subsignal("b", Pins("H4")),
        IOStandard("LVCMOS33"),
    ),

    ("rgb_led", 3,
        Subsignal("r", Pins("K1")),
        Subsignal("g", Pins("H6")),
        Subsignal("b", Pins("K2")),
        IOStandard("LVCMOS33"),
    ),

    ("user_sw", 0, Pins("A8"),  IOStandard("LVCMOS33")),
    ("user_sw", 1, Pins("C11"), IOStandard("LVCMOS33")),
    ("user_sw", 2, Pins("C10"), IOStandard("LVCMOS33")),
    ("user_sw", 3, Pins("A10"), IOStandard("LVCMOS33")),

    ("user_btn", 0, Pins("D9"), IOStandard("LVCMOS33")),
    ("user_btn", 1, Pins("C9"), IOStandard("LVCMOS33")),
    ("user_btn", 2, Pins("B9"), IOStandard("LVCMOS33")),
    ("user_btn", 3, Pins("B8"), IOStandard("LVCMOS33")),

    ("clk100", 0, Pins("E3"), IOStandard("LVCMOS33")),

    ("cpu_reset", 0, Pins("C2"), IOStandard("LVCMOS33")),

    ("serial", 0,
        Subsignal("tx", Pins("D10")),
        Subsignal("rx", Pins("A9")),
        IOStandard("LVCMOS33")
    ),

    ("spi", 0,
        Subsignal("clk",  Pins("F1")),
        Subsignal("cs_n", Pins("C1")),
        Subsignal("mosi", Pins("H1")),
        Subsignal("miso", Pins("G1")),
        IOStandard("LVCMOS33"),
    ),

    ("i2c", 0,
        Subsignal("scl", Pins("L18")),
        Subsignal("sda", Pins("M18")),
        Subsignal("scl_pup", Pins("A14")),
        Subsignal("sda_pup", Pins("A13")),
        IOStandard("LVCMOS33"),
    ),

    ("spiflash4x", 0,
        Subsignal("cs_n", Pins("L13")),
        Subsignal("clk",  Pins("L16")),
        Subsignal("dq",   Pins("K17", "K18", "L14", "M14")),
        IOStandard("LVCMOS33")
    ),
    ("spiflash", 0,
        Subsignal("cs_n", Pins("L13")),
        Subsignal("clk",  Pins("L16")),
        Subsignal("mosi", Pins("K17")),
        Subsignal("miso", Pins("K18")),
        Subsignal("wp",   Pins("L14")),
        Subsignal("hold", Pins("M14")),
        IOStandard("LVCMOS33"),
    ),

    ("ddram", 0,
        Subsignal("a", Pins(
            "R2 M6 N4 T1 N6 R7 V6 U7",
            "R8 V7 R6 U6 T6 T8"),
            IOStandard("SSTL135")),
        Subsignal("ba",    Pins("R1 P4 P2"), IOStandard("SSTL135")),
        Subsignal("ras_n", Pins("P3"), IOStandard("SSTL135")),
        Subsignal("cas_n", Pins("M4"), IOStandard("SSTL135")),
        Subsignal("we_n",  Pins("P5"), IOStandard("SSTL135")),
        Subsignal("cs_n",  Pins("U8"), IOStandard("SSTL135")),
        Subsignal("dm", Pins("L1 U1"), IOStandard("SSTL135")),
        Subsignal("dq", Pins(
            "K5 L3 K3 L6 M3 M1 L4 M2",
            "V4 T5 U4 V5 V1 T3 U3 R3"),
            IOStandard("SSTL135"),
            Misc("IN_TERM=UNTUNED_SPLIT_40")),
        Subsignal("dqs_p", Pins("N2 U2"),
            IOStandard("DIFF_SSTL135"),
            Misc("IN_TERM=UNTUNED_SPLIT_40")),
        Subsignal("dqs_n", Pins("N1 V2"),
            IOStandard("DIFF_SSTL135"),
            Misc("IN_TERM=UNTUNED_SPLIT_40")),
        Subsignal("clk_p", Pins("U9"), IOStandard("DIFF_SSTL135")),
        Subsignal("clk_n", Pins("V9"), IOStandard("DIFF_SSTL135")),
        Subsignal("cke",   Pins("N5"), IOStandard("SSTL135")),
        Subsignal("odt",   Pins("R5"), IOStandard("SSTL135")),
        Subsignal("reset_n", Pins("K6"), IOStandard("SSTL135")),
        Misc("SLEW=FAST"),
    ),

    ("eth_ref_clk", 0, Pins("G18"), IOStandard("LVCMOS33")),
    ("eth_clocks", 0,
        Subsignal("tx", Pins("H16")),
        Subsignal("rx", Pins("F15")),
        IOStandard("LVCMOS33"),
    ),
    ("eth", 0,
        Subsignal("rst_n",   Pins("C16")),
        Subsignal("mdio",    Pins("K13")),
        Subsignal("mdc",     Pins("F16")),
        Subsignal("rx_dv",   Pins("G16")),
        Subsignal("rx_er",   Pins("C17")),
        Subsignal("rx_data", Pins("D18 E17 E18 G17")),
        Subsignal("tx_en",   Pins("H15")),
        Subsignal("tx_data", Pins("H14 J14 J13 H17")),
        Subsignal("col",     Pins("D17")),
        Subsignal("crs",     Pins("G14")),
        IOStandard("LVCMOS33"),
    ),
]

_sdcard_pmod_io = [ # https://store.digilentinc.com/pmod-microsd-microsd-card-slot/
    ("sdcard", 0,
        Subsignal("data", Pins("D15 J17 J18 E15")),
        Subsignal("cmd", Pins("E16")),
        Subsignal("clk", Pins("C15")),
        Subsignal("cd", Pins("K15")),
        IOStandard("LVCMOS33"), Misc("SLEW=FAST")
    ),
]

# Connectors ---------------------------------------------------------------------------------------

_connectors = [
    ("pmoda", "G13 B11 A11 D12 D13 B18 A18 K16"),
    ("pmodb", "E15 E16 D15 C15 J17 J18 K15 J15"),
    ("pmodc", "U12 V12 V10 V11 U14 V14 T13 U13"),
    ("pmodd", "D4 D3 F4 F3 E2 D2 H2 G2"),
    ("ck_io", {
        # Outer Digital Header
        "ck_io0"  : "V15",
        "ck_io1"  : "U16",
        "ck_io2"  : "P14",
        "ck_io3"  : "T11",
        "ck_io4"  : "R12",
        "ck_io5"  : "T14",
        "ck_io6"  : "T15",
        "ck_io7"  : "T16",
        "ck_io8"  : "N15",
        "ck_io9"  : "M16",
        "ck_io10" : "V17",
        "ck_io11" : "U18",
        "ck_io12" : "R17",
        "ck_io13" : "P17",

        # Inner Digital Header
        "ck_io26" : "U11",
        "ck_io27" : "V16",
        "ck_io28" : "M13",
        "ck_io29" : "R10",
        "ck_io30" : "R11",
        "ck_io31" : "R13",
        "ck_io32" : "R15",
        "ck_io33" : "P15",
        "ck_io34" : "R16",
        "ck_io35" : "N16",
        "ck_io36" : "N14",
        "ck_io37" : "U17",
        "ck_io38" : "T18",
        "ck_io39" : "R18",
        "ck_io40" : "P18",
        "ck_io41" : "N17",

        # Outer Analog Header as Digital IO
        "ck_a0" : "F5",
        "ck_a1" : "D8",
        "ck_a2" : "C7",
        "ck_a3" : "E7",
        "ck_a4" : "D7",
        "ck_a5" : "D5",

        # Inner Analog Header as Digital IO
        "ck_io20" : "B7",
        "ck_io21" : "B6",
        "ck_io22" : "E6",
        "ck_io23" : "E5",
        "ck_io24" : "A4",
        "ck_io25" : "A3",
        } ),
    ("XADC", {
        # Outer Analog Header
        "vaux4_n"  : "C5",
        "vaux4_p"  : "C6",
        "vaux5_n"  : "A5",
        "vaux5_p"  : "A6",
        "vaux6_n"  : "B4",
        "vaux6_p"  : "C4",
        "vaux7_n"  : "A1",
        "vaux7_p"  : "B1",
        "vaux15_n" : "B2",
        "vaux15_p" : "B3",
        "vaux0_n"  : "C14",
        "vaux0_p"  : "D14",

        # Inner Analog Header
        "vaux12_n" : "B7",
        "vaux12_p" : "B6",
        "vaux13_n" : "E6",
        "vaux13_p" : "E5",
        "vaux14_n" : "A4",
        "vaux14_p" : "A3",

        # Power Measurements
        "vsnsuv_n"   : "B17",
        "vsnsuv_p"   : "B16",
        "vsns5v0_n"  : "B12",
        "vsns5v0_p"  : "C12",
        "isns5v0_n"  : "F14",
        "isns5v0_n"  : "F13",
        "isns0v95_n" : "A16",
        "isns0v95_n" : "A15",
        } ),
]

# Platform -----------------------------------------------------------------------------------------

class Platform(XilinxPlatform):
    default_clk_name   = "clk100"
    default_clk_period = 1e9/100e6

    def __init__(self, variant="a7-35"):
        device = {
            "a7-35":  "xc7a35ticsg324-1L",
            "a7-100": "xc7a100tcsg324-1"
        }[variant]
        XilinxPlatform.__init__(self, device, _io, _connectors, toolchain="vivado")
        self.toolchain.bitstream_commands = \
            ["set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]"]
        self.toolchain.additional_commands = \
            ["write_cfgmem -force -format bin -interface spix4 -size 16 "
             "-loadbit \"up 0x0 {build_name}.bit\" -file {build_name}.bin"]
        self.add_platform_command("set_property INTERNAL_VREF 0.675 [get_iobanks 34]")

    def create_programmer(self):
        bscan_spi = "bscan_spi_xc7a100t.bit" if "xc7a100t" in self.device else "bscan_spi_xc7a35t.bit"
        return OpenOCD("openocd_xc7_ft2232.cfg", bscan_spi)

    def do_finalize(self, fragment):
        XilinxPlatform.do_finalize(self, fragment)
        self.add_period_constraint(self.lookup_request("clk100", loose=True), 1e9/100e6)
