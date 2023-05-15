#
# This file is part of LiteX.
#
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen.fhdl.module import Module
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import *

# OS-FPGA AsyncResetSynchronizer -------------------------------------------------------------------

class OSFPGAAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        self.comb += cd.rst.eq(async_reset) # FIXME: Implement.

class OSFPGAAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return OSFPGAAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

# OS-FPGA Special Overrides -------------------------------------------------------------------------

osfpga_special_overrides = {
    AsyncResetSynchronizer: OSFPGAAsyncResetSynchronizer,
}
