from migen.fhdl.module import Module
from migen.fhdl.specials import Instance
from migen.genlib.io import DifferentialInput, DifferentialOutput


class AlteraDifferentialInputImpl(Module):
    def __init__(self, i_p, i_n, o):
        self.specials += Instance("ALT_INBUF_DIFF",
                                  name="ibuf_diff",
                                  i_i=i_p,
                                  i_ibar=i_n,
                                  o_o=o)


class AlteraDifferentialInput:
    @staticmethod
    def lower(dr):
        return AlteraDifferentialInputImpl(dr.i_p, dr.i_n, dr.o)


class AlteraDifferentialOutputImpl(Module):
    def __init__(self, i, o_p, o_n):
        self.specials += Instance("ALT_OUTBUF_DIFF",
                                  name="obuf_diff",
                                  i_i=i,
                                  o_o=o_p,
                                  o_obar=o_n)


class AlteraDifferentialOutput:
    @staticmethod
    def lower(dr):
        return AlteraDifferentialOutputImpl(dr.i, dr.o_p, dr.o_n)


altera_special_overrides = {
    DifferentialInput: AlteraDifferentialInput,
    DifferentialOutput: AlteraDifferentialOutput
}
