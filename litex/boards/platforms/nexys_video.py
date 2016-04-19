# This file is Copyright (c) 2015 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform, XC3SProg, VivadoProgrammer

_io = [
    ("user_led", 0, Pins("T14"), IOStandard("LVCMOS25")),
    ("user_led", 1, Pins("T15"), IOStandard("LVCMOS25")),
    ("user_led", 2, Pins("T16"), IOStandard("LVCMOS25")),
    ("user_led", 3, Pins("U16"), IOStandard("LVCMOS25")),
    ("user_led", 4, Pins("V15"), IOStandard("LVCMOS25")),
    ("user_led", 5, Pins("W16"), IOStandard("LVCMOS25")),
    ("user_led", 6, Pins("W15"), IOStandard("LVCMOS25")),
    ("user_led", 7, Pins("Y13"), IOStandard("LVCMOS25")),

    ("user_sw", 0, Pins("E22"), IOStandard("LVCMOS12")),
    ("user_sw", 1, Pins("F21"), IOStandard("LVCMOS12")),
    ("user_sw", 2, Pins("G21"), IOStandard("LVCMOS12")),
    ("user_sw", 3, Pins("G22"), IOStandard("LVCMOS12")),
    ("user_sw", 4, Pins("H17"), IOStandard("LVCMOS12")),
    ("user_sw", 5, Pins("J16"), IOStandard("LVCMOS12")),
    ("user_sw", 6, Pins("K13"), IOStandard("LVCMOS12")),
    ("user_sw", 7, Pins("M17"), IOStandard("LVCMOS12")),


    ("user_btn", 0, Pins("B22"), IOStandard("LVCMOS12")),
    ("user_btn", 1, Pins("D22"), IOStandard("LVCMOS12")),
    ("user_btn", 2, Pins("C22"), IOStandard("LVCMOS12")),
    ("user_btn", 3, Pins("D14"), IOStandard("LVCMOS12")),
    ("user_btn", 4, Pins("F15"), IOStandard("LVCMOS12")),
    ("user_btn", 5, Pins("G4"),  IOStandard("LVCMOS12")),

    ("oled", 0,
        Subsignal("dc",   Pins("W22")),
        Subsignal("res",  Pins("U21")),
        Subsignal("sclk", Pins("W21")),
        Subsignal("sdin", Pins("Y22")),
        Subsignal("vbat", Pins("P20")),
        Subsignal("vdd",  Pins("V22")),
        IOStandard("LVCMOS33")
    ),

    ("clk100", 0, Pins("R4"), IOStandard("LVCMOS33")),

    ("cpu_reset", 0, Pins("G4"), IOStandard("LVCMOS15")),

    ("serial", 0,
        Subsignal("tx", Pins("AA19")),
        Subsignal("rx", Pins("V18")),
        IOStandard("LVCMOS33"),
    ),

    ("ddram", 0,
        Subsignal("a", Pins(
            "M2 M5 M3 M1 L6 P1 N3 N2",
            "M6 R1 L5 N5 N4 P2 P6"),
            IOStandard("SSTL15")),
        Subsignal("ba", Pins("L3 K6 L4"), IOStandard("SSTL15")),
        Subsignal("ras_n", Pins("J4"), IOStandard("SSTL15")),
        Subsignal("cas_n", Pins("K3"), IOStandard("SSTL15")),
        Subsignal("we_n", Pins("L1"), IOStandard("SSTL15")),
        Subsignal("dm", Pins("G3 F1"), IOStandard("SSTL15")),
        Subsignal("dq", Pins(
            "G2 H4 H5 J1 K1 H3 H2 J5",
            "E3 B2 F3 D2 C2 A1 E2 B1"),
            IOStandard("SSTL15"),
            Misc("IN_TERM=UNTUNED_SPLIT_50")),
        Subsignal("dqs_p", Pins("K2 E1"), IOStandard("DIFF_SSTL15")),
        Subsignal("dqs_n", Pins("J2 D1"), IOStandard("DIFF_SSTL15")),
        Subsignal("clk_p", Pins("P5"), IOStandard("DIFF_SSTL15")),
        Subsignal("clk_n", Pins("P4"), IOStandard("DIFF_SSTL15")),
        Subsignal("cke", Pins("J6"), IOStandard("SSTL15")),
        Subsignal("odt", Pins("K4"), IOStandard("SSTL15")),
        Subsignal("reset_n", Pins("G1"), IOStandard("SSTL15")),
        Misc("SLEW=FAST"),
    ),

    ("eth_clocks", 0,
        Subsignal("tx", Pins("AA14")),
        Subsignal("rx", Pins("V13")),
        IOStandard("LVCMOS25")
    ),
    ("eth", 0,
        Subsignal("rst_n", Pins("U7"), IOStandard("LVCMOS33")),
        Subsignal("int_n", Pins("Y14")),
        Subsignal("mdio", Pins("Y16")),
        Subsignal("mdc", Pins("AA16")),
        Subsignal("rx_ctl", Pins("W10")),
        Subsignal("rx_data", Pins("AB16 AA15 AB15 AB11")),
        Subsignal("tx_ctl", Pins("V10")),
        Subsignal("tx_data", Pins("Y12 W12 W11 Y11")),
        IOStandard("LVCMOS25")
    ),

    ("hdmi_in", 0,
        Subsignal("clk_p", Pins("V4"), IOStandard("TDMS")),
        Subsignal("clk_n", Pins("W4"), IOStandard("TDMS")),
        Subsignal("data0_p", Pins("Y3"), IOStandard("TDMS")),
        Subsignal("data0_n", Pins("AA3"), IOStandard("TDMS")),
        Subsignal("data1_p", Pins("W2"), IOStandard("TDMS")),
        Subsignal("data1_n", Pins("Y2"), IOStandard("TDMS")),
        Subsignal("data2_p", Pins("U2"), IOStandard("TDMS")),
        Subsignal("data2_n", Pins("V2"), IOStandard("TDMS")),
        Subsignal("scl", Pins("Y4"), IOStandard("LVCMOS33")),
        Subsignal("sda", Pins("AB5"), IOStandard("LVCMOS33")),
        Subsignal("cec", Pins("AA5"), IOStandard("LVCMOS33")),  # FIXME
        Subsignal("txen", Pins("R3"), IOStandard("LVCMOS33")),  # FIXME
        Subsignal("hpa", Pins("AB12"), IOStandard("LVCMOS33")), # FIXME
    ),

    ("hdmi_out", 0,
        Subsignal("clk_p", Pins("T1"), IOStandard("TMDS")),
        Subsignal("clk_n", Pins("U1"), IOStandard("TMDS")),
        Subsignal("data0_p", Pins("W1"), IOStandard("TMDS")),
        Subsignal("data0_n", Pins("Y1"), IOStandard("TMDS")),
        Subsignal("data1_p", Pins("AA1"), IOStandard("TMDS")),
        Subsignal("data1_n", Pins("AB1"), IOStandard("TMDS")),
        Subsignal("data2_p", Pins("AB3"), IOStandard("TMDS")),
        Subsignal("data2_n", Pins("AB2"), IOStandard("TMDS")),
        Subsignal("scl", Pins("U3"), IOStandard("LVCMOS33")),
        Subsignal("sda", Pins("V3"), IOStandard("LVCMOS33")),
        Subsignal("cec", Pins("AA4"), IOStandard("LVCMOS33")),  # FIXME
        Subsignal("hdp", Pins("AB13"), IOStandard("LVCMOS25")), # FIXME
    ),
]


class Platform(XilinxPlatform):
    default_clk_name = "clk100"
    default_clk_period = 10.0

    def __init__(self, toolchain="vivado", programmer="vivado"):
        XilinxPlatform.__init__(self, "xc7a200t-sbg484-1", _io,
                                toolchain=toolchain)
        self.toolchain.bitstream_commands = \
            ["set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]"]
        self.toolchain.additional_commands = \
            ["write_cfgmem -force -format bin -interface spix4 -size 16 "
             "-loadbit \"up 0x0 {build_name}.bit\" -file {build_name}.bin"]
        self.programmer = programmer
        self.add_platform_command("set_property INTERNAL_VREF 0.750 [get_iobanks 35]")


    def create_programmer(self):
        if self.programmer == "xc3sprog":
            return XC3SProg("nexys4")
        elif self.programmer == "vivado":
            return VivadoProgrammer(flash_part="n25q128-3.3v-spi-x1_x2_x4")
        else:
            raise ValueError("{} programmer is not supported"
                             .format(self.programmer))

    def do_finalize(self, fragment):
        XilinxPlatform.do_finalize(self, fragment)
        try:
            self.add_period_constraint(self.lookup_request("eth_clocks").rx, 8.0)
        except ConstraintError:
            pass
