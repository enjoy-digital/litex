from migen.fhdl.std import *
from migen.genlib.fsm import *
from migen.actorlib.fifo import *
from migen.flow.actor import EndpointDescription

user_layout = EndpointDescription(
    [    ("dst", 8),
         ("length", 4*8),
         ("error", 1),
        ("d", 8)
    ],
    packetized=True
)

phy_layout = [
    ("d", 8)
]


class LiteUSBPipe:
    def __init__(self, layout):
        self.sink = Sink(layout)
        self.source = Source(layout)


class LiteUSBTimeout(Module):
    def __init__(self, clk_freq, length):
        cnt_max = int(clk_freq*length)
        width = bits_for(cnt_max)

        self.clear = Signal()
        self.done = Signal()

        cnt = Signal(width)
        self.sync += \
            If(self.clear,
                cnt.eq(0)
            ).Elif(~self.done,
                cnt.eq(cnt+1)
            )
        self.comb += self.done.eq(cnt == cnt_max)

#
# TB
#
import random


def randn(max_n):
    return random.randint(0, max_n-1)


class RandRun:
    def __init__(self, level=0):
        self.run = True
        self.level = level

    def do_simulation(self, selfp):
        self.run = True
        n = randn(100)
        if n < self.level:
            self.run = False
