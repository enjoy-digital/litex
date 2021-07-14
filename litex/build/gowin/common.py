#
# This file is part of LiteX.
#
# Copyright (c) 2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen.fhdl.module import Module
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import *

# Gowin AsyncResetSynchronizer ---------------------------------------------------------------------

class GowinAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst1 = Signal()
        self.specials += [
            Instance("DFFP",
                i_D      = 0,
                i_PRESET = async_reset,
                i_CLK    = cd.clk,
                o_Q      = rst1),
            Instance("DFFP",
                i_D      = rst1,
                i_PRESET = async_reset,
                i_CLK    = cd.clk,
                o_Q      = cd.rst)
        ]


class GowinAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return GowinAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

# Gowin Special Overrides --------------------------------------------------------------------------

gowin_special_overrides = {
    AsyncResetSynchronizer: GowinAsyncResetSynchronizer,
}