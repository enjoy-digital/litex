from migen import *
from migen.genlib.record import Record

from misoc.cores.dvi_sampler.common import control_tokens, channel_layout


class Decoding(Module):
    def __init__(self):
        self.valid_i = Signal()
        self.input = Signal(10)
        self.valid_o = Signal()
        self.output = Record(channel_layout)

        ###

        self.sync.pix += self.output.de.eq(1)
        for i, t in enumerate(control_tokens):
            self.sync.pix += If(self.input == t,
                self.output.de.eq(0),
                self.output.c.eq(i)
            )
        self.sync.pix += self.output.d[0].eq(self.input[0] ^ self.input[9])
        for i in range(1, 8):
            self.sync.pix += self.output.d[i].eq(self.input[i] ^ self.input[i-1] ^ ~self.input[8])
        self.sync.pix += self.valid_o.eq(self.valid_i)
