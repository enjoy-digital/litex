from migen import *
from migen.fhdl.specials import Special
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import *

# AsyncResetSynchronizer ---------------------------------------------------------------------

class SimAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        self.clock_domains.cd_resync = ClockDomain(reset_less=True)
        self.comb += self.cd_resync.clk.eq(cd.clk)
        rst1 = Signal()
        self.sync.resync += [
            rst1.eq(async_reset),
            cd.rst.eq(async_reset | rst1)
        ]

class SimAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return SimAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

# DDROutput ----------------------------------------------------------------------------------------

class SimDDROutputImpl(Module):
    def __init__(self, o, i1, i2, clk):
        self.specials += Instance("DDR_OUTPUT",
            i_i1  = i1,
            i_i2  = i2,
            o_o   = o,
            i_clk = clk
        )

class SimDDROutput:
    @staticmethod
    def lower(dr):
        return SimDDROutputImpl(dr.o, dr.i1, dr.i2, dr.clk)

# DDRInput -----------------------------------------------------------------------------------------

class SimDDRInputImpl(Module):
    def __init__(self, i, o1, o2, clk):
        self.specials += Instance("DDR_INPUT",
            o_o1  = o1,
            o_o2  = o2,
            i_i   = i,
            i_clk = clk
        )

class SimDDRInput:
    @staticmethod
    def lower(dr):
        return SimDDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)

# Special Overrides --------------------------------------------------------------------------------

sim_special_overrides = {
    AsyncResetSynchronizer : SimAsyncResetSynchronizer,
    DDROutput              : SimDDROutput,
    DDRInput               : SimDDRInput,
}
