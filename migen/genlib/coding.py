"""
Encoders and decoders between binary and one-hot representation
"""

from migen.fhdl.structure import *
from migen.fhdl.module import Module


class Encoder(Module):
    """Encode one-hot to binary

    If `n` is low, the `o` th bit in `i` is asserted, else none or
    multiple bits are asserted.

    Parameters
    ----------
    width : int
        Bit width of the input

    Attributes
    ----------
    i : Signal(width), in
        One-hot input
    o : Signal(max=width), out
        Encoded binary
    n : Signal(1), out
        Invalid, either none or multiple input bits are asserted
    """
    def __init__(self, width):
        self.i = Signal(width)  # one-hot
        self.o = Signal(max=max(2, width))  # binary
        self.n = Signal()  # invalid: none or multiple
        act = dict((1<<j, self.o.eq(j)) for j in range(width))
        act["default"] = self.n.eq(1)
        self.comb += Case(self.i, act)


class PriorityEncoder(Module):
    """Priority encode requests to binary

    If `n` is low, the `o` th bit in `i` is asserted and the bits below
    `o` are unasserted, else `o == 0`. The LSB has priority.

    Parameters
    ----------
    width : int
        Bit width of the input

    Attributes
    ----------
    i : Signal(width), in
        Input requests
    o : Signal(max=width), out
        Encoded binary
    n : Signal(1), out
        Invalid, no input bits are asserted
    """
    def __init__(self, width):
        self.i = Signal(width)  # one-hot, lsb has priority
        self.o = Signal(max=max(2, width))  # binary
        self.n = Signal()  # none
        for j in range(width)[::-1]:  # last has priority
            self.comb += If(self.i[j], self.o.eq(j))
        self.comb += self.n.eq(self.i == 0)


class Decoder(Module):
    """Decode binary to one-hot

    If `n` is low, the `i` th bit in `o` is asserted, the others are
    not, else `o == 0`.

    Parameters
    ----------
    width : int
        Bit width of the output

    Attributes
    ----------
    i : Signal(max=width), in
        Input binary
    o : Signal(width), out
        Decoded one-hot
    n : Signal(1), in
        Invalid, no output bits are to be asserted
    """

    def __init__(self, width):
        self.i = Signal(max=max(2, width))  # binary
        self.n = Signal()  # none/invalid
        self.o = Signal(width)  # one-hot
        act = dict((j, self.o.eq(1<<j)) for j in range(width))
        self.comb += Case(self.i, act)
        self.comb += If(self.n, self.o.eq(0))


class PriorityDecoder(Decoder):
    pass  # same
