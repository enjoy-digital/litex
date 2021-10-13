#
# This file is part of LiteX.
#
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen.fhdl.module import Module
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import *

# Efinix AsyncResetSynchronizer ---------------------------------------------------------------------

class EfinixAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst1 = Signal()
        self.specials += [
            Instance("EFX_FF",
                i_D      = 0,
                i_SR     = async_reset,
                i_CLK    = cd.clk,
                i_CE     = 1,
                o_Q      = rst1),
            Instance("EFX_FF",
                i_D      = rst1,
                i_SR     = async_reset,
                i_CLK    = cd.clk,
                i_CE     = 1,
                o_Q      = cd.rst)
        ]


class EfinixAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return EfinixAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

# Gowin Special Overrides --------------------------------------------------------------------------

efinix_special_overrides = {
    AsyncResetSynchronizer: EfinixAsyncResetSynchronizer
}
