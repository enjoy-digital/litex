#
# This file is part of LiteX.
#
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

# AsyncResetSynchronizer ---------------------------------------------------------------------------

class MicrosemiPolarfireAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst1 = Signal()
        self.specials += [
            Instance("DFN1P0",
                i_CLK = cd.clk,
                i_PRE = ~async_reset,
                i_D   = 0,
                o_Q   = rst1
            ),
            Instance("DFN1P0",
                i_CLK = cd.clk,
                i_PRE = ~async_reset,
                i_D   = rst1,
                o_Q   = cd.rst
            )
        ]


class MicrosemiPolarfireAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return MicrosemiPolarfireAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

# Special Overrides --------------------------------------------------------------------------------

microsemi_polarfire_special_overrides = {
    AsyncResetSynchronizer: MicrosemiPolarfireAsyncResetSynchronizer,
}
