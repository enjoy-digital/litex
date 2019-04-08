from migen.fhdl.module import Module
from migen.fhdl.specials import Instance
from migen.genlib.io import DifferentialInput, DifferentialOutput
from migen.genlib.resetsync import AsyncResetSynchronizer

from migen.fhdl.structure import *


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

class AlteraAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        if not hasattr(async_reset, "attr"):
            i, async_reset = async_reset, Signal()
            self.comb += async_reset.eq(i)
        rst_meta = Signal()
        self.specials += [
            Instance("DFF", i_d=0, i_clk=cd.clk, i_clrn=1,
                     i_prn=async_reset, o_q=rst_meta,
                     attr={"async_reg", "ars_ff1"}),
            Instance("DFF", i_d=rst_meta, i_clk=cd.clk, i_clrn=1,
                     i_prn=async_reset,  o_q=cd.rst,
                     attr={"async_reg", "ars_ff2"})
        ]

class AlteraAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return AlteraAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)


altera_special_overrides = {
    DifferentialInput: AlteraDifferentialInput,
    DifferentialOutput: AlteraDifferentialOutput,
    AsyncResetSynchronizer: AlteraAsyncResetSynchronizer
}
