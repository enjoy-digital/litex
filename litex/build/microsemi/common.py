from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer


class MicrosemiPolarfireAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst1 = Signal()
        self.specials += [
            Instance("DFN1P0", i_D=0, i_PRE=~async_reset,
                     i_CLK=cd.clk, o_Q=rst1),
            Instance("DFN1P0", i_D=rst1, i_PRE=~async_reset,
                     i_CLK=cd.clk, o_Q=cd.rst)
        ]


class MicrosemiPolarfireAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return MicrosemiPolarfireAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)


microsemi_polarfire_special_overrides = {
    AsyncResetSynchronizer: MicrosemiPolarfireAsyncResetSynchronizer,
}
