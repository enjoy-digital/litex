from litex.build.generic_platform import *
from litex.build.sim import SimPlatform


class SimPins(Pins):
    def __init__(self, n):
        Pins.__init__(self, "s "*n)

_io = [
    ("sys_clk", 0, SimPins(1)),
    ("sys_rst", 0, SimPins(1)),
    ("serial", 0,
        Subsignal("source_valid", SimPins(1)),
        Subsignal("source_ready", SimPins(1)),
        Subsignal("source_data", SimPins(8)),

        Subsignal("sink_valid", SimPins(1)),
        Subsignal("sink_ready", SimPins(1)),
        Subsignal("sink_data", SimPins(8)),
    ),
    ("eth_clocks", 0,
        Subsignal("none", SimPins(1)),
    ),
    ("eth", 0,
        Subsignal("source_valid", SimPins(1)),
        Subsignal("source_ready", SimPins(1)),
        Subsignal("source_data", SimPins(8)),

        Subsignal("sink_valid", SimPins(1)),
        Subsignal("sink_ready", SimPins(1)),
        Subsignal("sink_data", SimPins(8)),
    ),
    ("eth_clocks", 1,
        Subsignal("none", SimPins(1)),
    ),
    ("eth", 1,
        Subsignal("source_valid", SimPins(1)),
        Subsignal("source_ready", SimPins(1)),
        Subsignal("source_data", SimPins(8)),

        Subsignal("sink_valid", SimPins(1)),
        Subsignal("sink_ready", SimPins(1)),
        Subsignal("sink_data", SimPins(8)),
    ),
    ("vga", 0,
        Subsignal("de", SimPins(1)),
        Subsignal("hsync", SimPins(1)),
        Subsignal("vsync", SimPins(1)),
        Subsignal("r", SimPins(8)),
        Subsignal("g", SimPins(8)),
        Subsignal("b", SimPins(8)),
    ),
]


class Platform(SimPlatform):
    default_clk_name = "sys_clk"
    default_clk_period = 1000  # on modern computers simulate at ~ 1MHz

    def __init__(self):
        SimPlatform.__init__(self, "SIM", _io)

    def do_finalize(self, fragment):
        pass
