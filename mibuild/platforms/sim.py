from mibuild.generic_platform import *
from mibuild.sim import SimPlatform


class SimPins(Pins):
    def __init__(self, n):
        Pins.__init__(self, "s "*n)

_io = [
    ("sys_clk", 0, SimPins(1)),
    ("sys_rst", 0, SimPins(1)),
    ("serial", 0,
        Subsignal("source_stb", SimPins(1)),
        Subsignal("source_ack", SimPins(1)),
        Subsignal("source_data", SimPins(8)),

        Subsignal("sink_stb", SimPins(1)),
        Subsignal("sink_ack", SimPins(1)),
        Subsignal("sink_data", SimPins(8)),
    ),
    ("eth_clocks", 0,
        Subsignal("none", SimPins(1)),
    ),
    ("eth", 0,
        Subsignal("source_stb", SimPins(1)),
        Subsignal("source_ack", SimPins(1)),
        Subsignal("source_data", SimPins(8)),

        Subsignal("sink_stb", SimPins(1)),
        Subsignal("sink_ack", SimPins(1)),
        Subsignal("sink_data", SimPins(8)),
    ),
]


class Platform(SimPlatform):
    is_sim = True
    default_clk_name = "sys_clk"
    default_clk_period = 1000  # on modern computers simulate at ~ 1MHz

    def __init__(self):
        SimPlatform.__init__(self, "SIM", _io)

    def do_finalize(self, fragment):
        pass
