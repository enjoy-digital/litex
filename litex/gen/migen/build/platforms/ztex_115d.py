from migen.build.generic_platform import *
from migen.build.xilinx import XilinxPlatform


_io = [
        ("clk_fx", 0, Pins("L22"), IOStandard("LVCMOS33")),
        ("clk_if", 0, Pins("K20"), IOStandard("LVCMOS33")),
        ("rst", 0, Pins("A18")),
        # PROG_B and DONE: AA1 U16

        ("fx2", 0,
            Subsignal("sloe", Pins("U15"), Drive(12)),  # M1
            Subsignal("slrd", Pins("N22"), Drive(12)),
            Subsignal("slwr", Pins("M22"), Drive(12)),
            Subsignal("pktend", Pins("AB5"), Drive(12)),  # CSO
            Subsignal("fifoadr", Pins("W17 Y18"), Drive(12)),  # CCLK M0
            Subsignal("cont", Pins("G20")),
            Subsignal("fd", Pins("Y17 V13 W13 AA8 AB8 W6 Y6 Y9 "
                "V21 V22 U20 U22 R20 R22 P18 P19")),
            Subsignal("flag", Pins("F20 F19 F18 AB17")),  # - - - CSI/MOSI
            Subsignal("rdy25", Pins("M21 K21 K22 J21")),
            Subsignal("ctl35", Pins("D19 E20 N20")),
            Subsignal("int45", Pins("C18 V17")),
            Subsignal("pc", Pins("G20 T10 V5 AB9 G19 H20 H19 H18")),
            # - DOUT/BUSY INIT_B RDWR_B DO CS CLK DI
            IOStandard("LVCMOS33")),

        ("mm", 0,
            Subsignal("a", Pins("M20 M19 M18 N19 T19 T21 T22 R19 ",
                        "P20 P21 P22 J22 H21 H22 G22 F21")),
            Subsignal("d", Pins("D20 C20 C19 B21 B20 J19 K19 L19"), Drive(2)),
            Subsignal("wr_n", Pins("C22")),
            Subsignal("rd_n", Pins("D21")),
            Subsignal("psen_n", Pins("D22")),
            IOStandard("LVCMOS33")),

        ("serial", 0,
            Subsignal("tx", Pins("B22"), Misc("SLEW=QUIETIO")),
            Subsignal("rx", Pins("A21"), Misc("PULLDOWN")),
            IOStandard("LVCMOS33")),

        ("ddram_clock", 0,
            Subsignal("p", Pins("F2"), Misc("OUT_TERM=UNTUNED_50")),
            Subsignal("n", Pins("F1"), Misc("OUT_TERM=UNTUNED_50")),
            IOStandard("SSTL18_II")),

        ("ddram", 0,
            Subsignal("dqs", Pins("L3 T2"), IOStandard("SSTL18_II"),  # DIFF_
                    Misc("IN_TERM=NONE")),
            Subsignal("dqs_n", Pins("L1 T1"), IOStandard("SSTL18_II"),  # DIFF_
                    Misc("IN_TERM=NONE")),
            Subsignal("dm", Pins("H1 H2"), Misc("OUT_TERM=UNTUNED_50")),
            Subsignal("dq", Pins("M1 M2 J1 K2 J3 K1 N3 N1 "
                    "U1 U3 P1 R3 P2 R1 V2 V1"), Misc("IN_TERM=NONE")),
            Subsignal("ras_n", Pins("N4"), Misc("OUT_TERM=UNTUNED_50")),
            Subsignal("cas_n", Pins("P3"), Misc("OUT_TERM=UNTUNED_50")),
            Subsignal("a", Pins("M5 K6 B1 J4 L4 K3 M4 K5 G3 G1 K4 C3 C1"),
                    Misc("OUT_TERM=UNTUNED_50")),
            Subsignal("ba", Pins("E3 E1 D1"), Misc("OUT_TERM=UNTUNED_50")),
            Subsignal("cke", Pins("J6"), Misc("OUT_TERM=UNTUNED_50")),
            Subsignal("cs_n", Pins("H6")),  # NC!
            Subsignal("odt", Pins("M3"), Misc("OUT_TERM=UNTUNED_50")),
            Subsignal("we_n", Pins("D2")),
            Subsignal("rzq", Pins("AA2")),
            Subsignal("zio", Pins("Y2")),
            IOStandard("SSTL18_II")),

        ("i2c", 0,
            Subsignal("scl", Pins("F22")),
            Subsignal("sda", Pins("E22")),
            IOStandard("LVCMOS33")),

        ("sd", 0,
            Subsignal("sck", Pins("H11")),
            Subsignal("d3", Pins("H14")),
            Subsignal("d", Pins("P10")),
            Subsignal("d1", Pins("T18")),
            Subsignal("d2", Pins("R17")),
            Subsignal("cmd", Pins("H13")),
            IOStandard("LVCMOS33")),

]


class Platform(XilinxPlatform):
    default_clk_name = "clk_if"
    default_clk_period = 20

    def __init__(self):
        XilinxPlatform.__init__(self, "xc6slx150-3csg484", _io)
        self.add_platform_command("""
CONFIG VCCAUX = "2.5";
""")

    def do_finalize(self, fragment):
        XilinxPlatform.do_finalize(self, fragment)

        try:
            clk_if = self.lookup_request("clk_if")
            clk_fx = self.lookup_request("clk_fx")
            self.add_platform_command("""
NET "{clk_if}" TNM_NET = "GRPclk_if";
NET "{clk_fx}" TNM_NET = "GRPclk_fx";
TIMESPEC "TSclk_fx" = PERIOD "GRPclk_fx" 20.83333 ns HIGH 50%;
TIMESPEC "TSclk_if" = PERIOD "GRPclk_if" 20 ns HIGH 50%;
TIMESPEC "TSclk_fx2if" = FROM "GRPclk_fx" TO "GRPclk_if" 3 ns DATAPATHONLY;
TIMESPEC "TSclk_if2fx" = FROM "GRPclk_if" TO "GRPclk_fx" 3 ns DATAPATHONLY;
""", clk_if=clk_if, clk_fx=clk_fx)
        except ConstraintError:
            pass
