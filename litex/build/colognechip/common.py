#
# This file is part of LiteX.
#
# Copyright (c) 2023 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen.fhdl.module import Module
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import *

# CologneChip AsyncResetSynchronizer ---------------------------------------------------------------

class CologneChipAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst1 = Signal()
        self.specials += [
            Instance("CC_DFF",
                p_CLK_INV = 0,
                p_EN_INV  = 0,
                p_SR_INV  = 0,
                p_SR_VAL  = 1,
                i_D       = 0,
                i_CLK     = cd.clk,
                i_EN      = 1,
                i_SR      = async_reset,
                o_Q       = rst1),
            Instance("CC_DFF",
                p_CLK_INV = 0,
                p_EN_INV  = 0,
                p_SR_INV  = 0,
                p_SR_VAL  = 1,
                i_D       = rst1,
                i_CLK     = cd.clk,
                i_EN      = 1,
                i_SR      = async_reset,
                o_Q       = cd.rst)
        ]

class CologneChipAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return CologneChipAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

# CologneChip DDR Input ----------------------------------------------------------------------------

class CologneChipDDRInputImpl(Module):
    def __init__(self, i, o1, o2, clk):
        for j in range(len(i)):
            self.specials += Instance("CC_IDDR",
                i_CLK = clk,
                i_D   = i[j] if len(i) > 1 else i,
                o_Q0  = o1[j] if len(o1) > 1 else o1,
                o_Q1  = o2[j] if len(o2) > 1 else o2,
            )

class CologneChipDDRInput:
    @staticmethod
    def lower(dr):
        return CologneChipDDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)

# CologneChip DDR Output ---------------------------------------------------------------------------

class CologneChipDDROutputImpl(Module):
    def __init__(self, i1, i2, o, clk):
        for j in range(len(o)):
            self.specials += Instance("CC_ODDR",
                p_CLK_INV = 0,
                i_CLK     = clk,
                i_DDR     = ~clk,
                i_D0      = i1[j] if len(i1) > 1 else i1,
                i_D1      = i2[j] if len(i2) > 1 else i2,
                o_Q       = o[j] if len(o) > 1 else o,
            )

class CologneChipDDROutput:
    @staticmethod
    def lower(dr):
        return CologneChipDDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)

# CologneChip Differential Input -------------------------------------------------------------------

class CologneChipDifferentialInputImpl(Module):
    def __init__(self, i_p, i_n, o):
        self.specials += Instance("CC_LVDS_IBUF",
            i_I_P = i_p,
            i_I_N = i_n,
            o_Y  = o,
        )

class CologneChipDifferentialInput:
    @staticmethod
    def lower(dr):
        return CologneChipDifferentialInputImpl(dr.i_p, dr.i_n, dr.o)

# CologneChip Differential Output ------------------------------------------------------------------

class CologneChipDifferentialOutputImpl(Module):
    def __init__(self, i, o_p, o_n):
        self.specials += Instance("CC_LVDS_OBUF",
            i_A  = i,
            o_O_P = o_p,
            o_O_N = o_n,
        )

class CologneChipDifferentialOutput:
    @staticmethod
    def lower(dr):
        return CologneChipDifferentialOutputImpl(dr.i, dr.o_p, dr.o_n)

# CologneChip SDR Input ----------------------------------------------------------------------------

class CologneChipSDRInputImpl(Module):
    def __init__(self, i, o):
        for j in range(len(i)):
            self.specials += Instance("CC_IBUF",
                i_I  = i[j] if len(i) > 1 else i,
                o_O = o[j] if len(o) > 1 else o,
            )

class CologneChipSDRInput:
    @staticmethod
    def lower(dr):
        return CologneChipSDRInput(dr.i, dr.o)

# CologneChip Special Overrides --------------------------------------------------------------------

colognechip_special_overrides = {
    AsyncResetSynchronizer: CologneChipAsyncResetSynchronizer,
    DDRInput:               CologneChipDDRInput,
    DDROutput:              CologneChipDDROutput,
    DifferentialInput:      CologneChipDifferentialInput,
    DifferentialOutput:     CologneChipDifferentialOutput,
    SDRInput:               CologneChipSDRInput,
}
