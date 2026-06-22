#
# This file is part of LiteX.
#
# Copyright (c) 2021 Miodrag Milanovic <mmicko@gmail.com>
# Copyright (c) 2015-2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen.fhdl.module import Module
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import *

# Anlogic AsyncResetSynchronizer -------------------------------------------------------------------

class AnlogicAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst1 = Signal()
        self.specials += [
            Instance("AL_MAP_SEQ",
                p_DFFMODE = "FF",
                p_REGSET  = "SET",
                p_SRMUX   = "SR",
                p_SRMODE  = "ASYNC",
                i_ce      = 1,
                i_d       = 0,
                i_sr      = async_reset,
                i_clk     = cd.clk,
                o_q       = rst1
            ),
            Instance("AL_MAP_SEQ",
                p_DFFMODE = "FF",
                p_REGSET  = "SET",
                p_SRMUX   = "SR",
                p_SRMODE  = "ASYNC",
                i_ce      = 1,
                i_d       = rst1,
                i_sr      = async_reset,
                i_clk     = cd.clk,
                o_q       = cd.rst
            )
        ]

class AnlogicAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return AnlogicAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

# Anlogic Special Overrides ------------------------------------------------------------------------

anlogic_special_overrides = {
    AsyncResetSynchronizer: AnlogicAsyncResetSynchronizer,
}
