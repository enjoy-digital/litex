# This file is Copyright (c) 2013 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen.build.generic_platform import *
from migen.build.lattice import LatticePlatform
from migen.build.lattice.programmer import LatticeProgrammer


_io = [
    ("clk100", 0, Pins("L5"), IOStandard("LVDS25")),
    ("rst_n", 0, Pins("A21"), IOStandard("LVCMOS33")),

    ("user_led", 0, Pins("Y20"), IOStandard("LVCMOS33")),
    ("user_led", 1, Pins("AA21"), IOStandard("LVCMOS33")),
    ("user_led", 2, Pins("U18"), IOStandard("LVCMOS33")),
    ("user_led", 3, Pins("U19"), IOStandard("LVCMOS33")),
    ("user_led", 4, Pins("W19"), IOStandard("LVCMOS33")),
    ("user_led", 5, Pins("V19"), IOStandard("LVCMOS33")),
    ("user_led", 6, Pins("AB20"), IOStandard("LVCMOS33")),
    ("user_led", 7, Pins("AA20"), IOStandard("LVCMOS33")),

    ("user_dip_btn", 0, Pins("J7"), IOStandard("LVCMOS15")),
    ("user_dip_btn", 1, Pins("J6"), IOStandard("LVCMOS15")),
    ("user_dip_btn", 2, Pins("H2"), IOStandard("LVCMOS15")),
    ("user_dip_btn", 3, Pins("H3"), IOStandard("LVCMOS15")),
    ("user_dip_btn", 4, Pins("J3"), IOStandard("LVCMOS15")),
    ("user_dip_btn", 5, Pins("K3"), IOStandard("LVCMOS15")),
    ("user_dip_btn", 6, Pins("J2"), IOStandard("LVCMOS15")),
    ("user_dip_btn", 7, Pins("J1"), IOStandard("LVCMOS15")),

    ("serial", 0,
        Subsignal("tx", Pins("B11"), IOStandard("LVCMOS33")),  # X4 IO0
        Subsignal("rx", Pins("B12"), IOStandard("LVCMOS33")),  # X4 IO1
    ),

    ("eth_clocks", 0,
        Subsignal("tx", Pins("C12")),
        Subsignal("gtx", Pins("M2")),
        Subsignal("rx", Pins("L4")),
        IOStandard("LVCMOS33")
    ),
    ("eth", 0,
        Subsignal("rst_n", Pins("L3")),
        Subsignal("mdio", Pins("L2")),
        Subsignal("mdc", Pins("V4")),
        Subsignal("dv", Pins("M1")),
        Subsignal("rx_er", Pins("M4")),
        Subsignal("rx_data", Pins("M5 N1 N6 P6 T2 R2 P5 P3")),
        Subsignal("tx_en", Pins("V3")),
        Subsignal("tx_data", Pins("V1 U1 R3 P1 N5 N3 N4 N2")),
        Subsignal("col", Pins("R1")),
        Subsignal("crs", Pins("P4")),
        IOStandard("LVCMOS33")
    ),

    ("eth_clocks", 1,
        Subsignal("tx", Pins("M21")),
        Subsignal("gtx", Pins("M19")),
        Subsignal("rx", Pins("N19")),
        IOStandard("LVCMOS33")
    ),
    ("eth", 1,
        Subsignal("rst_n", Pins("R21")),
        Subsignal("mdio", Pins("U16")),
        Subsignal("mdc", Pins("Y18")),
        Subsignal("dv", Pins("U15")),
        Subsignal("rx_er", Pins("V20")),
        Subsignal("rx_data", Pins("AB17 AA17 R19 V21 T17 R18 W21 Y21")),
        Subsignal("tx_en", Pins("V22")),
        Subsignal("tx_data", Pins("W22 R16 P17 Y22 T21 U22 P20 U20")),
        Subsignal("col", Pins("N18")),
        Subsignal("crs", Pins("P19")),
        IOStandard("LVCMOS33")
    ),
]


class Platform(LatticePlatform):
    default_clk_name = "clk100"
    default_clk_period = 10

    def __init__(self):
        LatticePlatform.__init__(self, "LFE3-35EA-6FN484C", _io)

    def do_finalize(self, fragment):
        LatticePlatform.do_finalize(self, fragment)
        try:
            self.add_period_constraint(self.lookup_request("eth_clocks", 0).rx, 8.0)
        except ConstraintError:
            pass
        try:
            self.add_period_constraint(self.lookup_request("eth_clocks", 1).rx, 8.0)
        except ConstraintError:
            pass
    def create_programmer(self):
        return LatticeProgrammer()
