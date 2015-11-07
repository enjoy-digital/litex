from migen.build.generic_platform import *
from migen.build.xilinx import XilinxPlatform


_io = [
        ("clk64", 0,
            Subsignal("p", Pins("R7")),
            Subsignal("n", Pins("T7")),
            IOStandard("LVDS_33"),
            Misc("DIFF_TERM=TRUE"),
        ),

        ("pps", 0, Pins("M14"), Misc("TIG")),
        ("reset_n", 0, Pins("D5"), Misc("TIG")),
        ("codec_reset", 0, Pins("B14")),
        # recycles fpga_cfg_cclk for reset from fw
        ("ext_reset", 0, Pins("R14")),

        ("i2c", 0,
            Subsignal("sda", Pins("T13")),
            Subsignal("scl", Pins("R13")),
        ),

        ("cgen", 0,
            Subsignal("st_ld", Pins("M13")),
            Subsignal("st_refmon", Pins("J14")),
            Subsignal("st_status", Pins("P6")),
            Subsignal("ref_sel", Pins("T2")),
            Subsignal("sync_b", Pins("H15")),
        ),

        ("fx2_ifclk", 0, Pins("T8")),
        ("fx2_gpif", 0,
            Subsignal("d", Pins("P8 P9 N9 T9 R9 P11 P13 N12 "
                                "T3 R3 P5 N6 T6 T5 N8 P7")),
            Subsignal("ctl", Pins("M7 M9 M11 P12")),
            Subsignal("slwr", Pins("T4")),  # rdy0
            Subsignal("slrd", Pins("R5")),  # rdy1
            # Subsignal("rdy2", Pins("T10")),
            # Subsignal("rdy3", Pins("N11")),
            # Subsignal("cs", Pins("P12")),
            Subsignal("sloe", Pins("R11")),
            Subsignal("pktend", Pins("P10")),
            Subsignal("adr", Pins("T11 H16")),
        ),

        ("user_led", 0, Pins("P4"), Misc("TIG")),
        ("user_led", 1, Pins("N4"), Misc("TIG")),
        ("user_led", 2, Pins("R2"), Misc("TIG")),

        ("debug_clk", 0, Pins("K15 K14")),
        ("debug", 0, Pins(
            "K16 J16 C16 C15 E13 D14 D16 D15 "
            "E14 F13 G13 F14 E16 F15 H13 G14 "
            "G16 F16 J12 J13 L14 L16 M15 M16 "
            "L13 K13 P16 N16 R15 P15 N13 N14")),

        ("adc", 0,
            Subsignal("sync", Pins("D10")),
            Subsignal("d", Pins("A4 B3 A3 D9 C10 A9 C9 D8 "
                                "C8 B8 A8 B15")),
        ),
        ("dac", 0,
            Subsignal("blank", Pins("K1")),
            Subsignal("sync", Pins("J2")),
            Subsignal("d", Pins("J1 H3 J3 G2 H1 N3 M4 R1 "
                                "P2 P1 M1 N1 M3 L4")),
        ),
        ("codec_spi", 0,
            Subsignal("sclk", Pins("K3")),
            Subsignal("sen", Pins("D13")),
            Subsignal("mosi", Pins("C13")),
            Subsignal("miso", Pins("G4")),
        ),

        ("aux_spi", 0,
            Subsignal("sen", Pins("C12")),
            Subsignal("sclk", Pins("D12")),
            Subsignal("miso", Pins("J5")),
        ),
        ("rx_io", 0, Pins("D7 C6 A6 B6 E9 A7 C7 B10 "
                          "A10 C11 A11 D11 B12 A12 A14 A13")),
        ("tx_io", 0, Pins("K4 L3 L2 F1 F3 G3 E3 E2 "
                          "E4 F4 D1 E1 D4 D3 C2 C1")),
        ("rx_spi", 0,
            Subsignal("miso", Pins("E6")),
            Subsignal("sen", Pins("B4")),
            Subsignal("mosi", Pins("A5")),
            Subsignal("sclk", Pins("C5")),
        ),
        ("tx_spi", 0,
            Subsignal("miso", Pins("J4")),
            Subsignal("sen", Pins("N2")),
            Subsignal("mosi", Pins("L1")),
            Subsignal("sclk", Pins("G1")),
        ),

        # these are just for information. do not request.
        ("mystery_bus", 0, Pins("C4 E7")),
        ("fpga_cfg",
            Subsignal("din", Pins("T14")),
            Subsignal("cclk", Pins("R14")),
            Subsignal("init_b", Pins("T12")),
            Subsignal("prog_b", Pins("A2")),
            Subsignal("done", Pins("T15")),
        ),
        ("jtag",
            Subsignal("tms", Pins("B2")),
            Subsignal("tdo", Pins("B16")),
            Subsignal("tdi", Pins("B1")),
            Subsignal("tck", Pins("A15")),
        ),
]


class Platform(XilinxPlatform):
    default_clk_name = "clk64"
    default_clk_period = 15.625

    def __init__(self):
        XilinxPlatform.__init__(self, "xc3s1400a-ft256-4", _io)
        self.toolchain.bitgen_opt = "-g LCK_cycle:6 -g Binary:Yes -w -g UnusedPin:PullUp"

    def do_finalize(self, fragment):
        XilinxPlatform.do_finalize(self, fragment)

        self.add_platform_command("""
TIMESPEC TS_Pad2Pad = FROM PADS TO PADS 7 ns;
""")

        try:
            ifclk = self.lookup_request("fx2_ifclk")
            gpif = self.lookup_request("fx2_gpif")
            for i, d in [(gpif.d, "in"), (gpif.d, "out"),
                    (gpif.ctl, "in"), (gpif.adr, "out"),
                    (gpif.slwr, "out"), (gpif.sloe, "out"),
                    (gpif.slrd, "out"), (gpif.pktend, "out")]:
                if len(i) > 1:
                    q = "(*)"
                else:
                    q = ""
                self.add_platform_command("""
INST "{i}%s" TNM = gpif_net_%s;
""" % (q, d), i=i)
            self.add_platform_command("""
NET "{ifclk}" TNM_NET = "GRPifclk";
TIMESPEC "TSifclk" = PERIOD "GRPifclk" 20833 ps HIGH 50%;
TIMEGRP "gpif_net_in" OFFSET = IN 5 ns VALID 10 ns BEFORE "{ifclk}" RISING;
TIMEGRP "gpif_net_out" OFFSET = OUT 7 ns AFTER "{ifclk}" RISING;
""", ifclk=ifclk)
        except ConstraintError:
             pass
