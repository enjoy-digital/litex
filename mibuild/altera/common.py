from migen.fhdl.std import Instance, Module
from migen.genlib.io import DifferentialInput, DifferentialOutput


class QuartusDifferentialInputImpl(Module):
    def __init__(self, i_p, i_n, o):
        self.specials += Instance("ALT_INBUF_DIFF",
                                  name="ibuf_diff",
                                  i_i=i_p,
                                  i_ibar=i_n,
                                  o_o=o)


class QuartusDifferentialInput:
    @staticmethod
    def lower(dr):
        return QuartusDifferentialInputImpl(dr.i_p, dr.i_n, dr.o)


class QuartusDifferentialOutputImpl(Module):
    def __init__(self, i, o_p, o_n):
        self.specials += Instance("ALT_OUTBUF_DIFF",
                                  name="obuf_diff",
                                  i_i=i,
                                  o_o=o_p,
                                  o_obar=o_n)


class QuartusDifferentialOutput:
    @staticmethod
    def lower(dr):
        return QuartusDifferentialOutputImpl(dr.i, dr.o_p, dr.o_n)


altera_special_overrides = {
    DifferentialInput: QuartusDifferentialInput,
    DifferentialOutput: QuartusDifferentialOutput
}
