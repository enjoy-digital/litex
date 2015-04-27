from migen.fhdl.std import *
from migen.genlib.fsm import *
from migen.actorlib.fifo import *
from migen.flow.actor import EndpointDescription
from migen.actorlib.packet import Arbiter, Dispatcher

user_layout = EndpointDescription(
    [("dst", 8),
     ("length", 4*8),
     ("error", 1),
     ("data", 8)
    ],
    packetized=True
)

phy_layout = [("data", 8)]


class LiteUSBPipe:
    def __init__(self, layout):
        self.sink = Sink(layout)
        self.source = Source(layout)

