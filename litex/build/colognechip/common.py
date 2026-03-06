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
            q1_d = Signal()
            # CC_IDDR:
            # Q0 is updated on clk rising edge
            # Q1 is updated on clk falling edge
            # To have something similar to SAME_EDGE or RESYNC
            # a CC_DFF is placed between Q1 and o2.
            self.specials += [
                Instance("CC_IDDR",
                    i_CLK = clk,
                    i_D   = i[j],
                    o_Q0  = o1[j],
                    o_Q1  = q1_d,
                ),
                Instance("CC_DFF",
                    p_CLK_INV = 0,
                    p_EN_INV  = 0,
                    p_SR_INV  = 0,
                    p_SR_VAL  = 0,
                    i_D       = q1_d,
                    i_CLK     = clk,
                    i_EN      = 1,
                    i_SR      = 0,
                    o_Q       = o2[j],
                ),
            ]

class CologneChipDDRInput:
    @staticmethod
    def lower(dr):
        return CologneChipDDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)

# CologneChip DDR Output ---------------------------------------------------------------------------

class CologneChipDDROutputImpl(Module):
    def __init__(self, i1, i2, o, clk):
        for j in range(len(o)):
            d1_d = Signal()
            # CC_ODDR:
            # D0 is updated on clk rising edge
            # D1 is updated on clk falling edge
            # To keep D1 stable between rising and falling edge,
            # and to have something similar to SAME_EDGE
            # a CC_DFF if placed between o2 and D1.
            self.specials += [
                Instance("CC_DFF",
                    p_CLK_INV = 0,
                    p_EN_INV  = 0,
                    p_SR_INV  = 0,
                    p_SR_VAL  = 0,
                    i_D       = i2[j],
                    i_CLK     = clk,
                    i_EN      = 1,
                    i_SR      = 0,
                    o_Q       = d1_d,
                ),
                Instance("CC_ODDR",
                    p_CLK_INV = 0,
                    i_CLK     = clk,
                    i_DDR     = clk,
                    i_D0      = i1[j],
                    i_D1      = d1_d,
                    o_Q       = o[j],
                )
            ]

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
    def __init__(self, i, o, clk):
        for j in range(len(i)):
            self.specials += [
                Instance("CC_DFF",
                    p_CLK_INV = 0,
                    p_EN_INV  = 0,
                    p_SR_INV  = 0,
                    p_SR_VAL  = 0,
                    i_D       = i[j],
                    i_CLK     = clk,
                    i_EN      = 1,
                    i_SR      = 0,
                    o_Q       = o[j],
                )
            ]

class CologneChipSDRInput:
    @staticmethod
    def lower(dr):
        return CologneChipSDRInputImpl(dr.i, dr.o, dr.clk)

# CologneChip SDR Output ----------------------------------------------------------------------------

class CologneChipSDROutputImpl(Module):
    def __init__(self, i, o, clk):
        for j in range(len(i)):
            self.specials += [
                Instance("CC_DFF",
                    p_CLK_INV = 0,
                    p_EN_INV  = 0,
                    p_SR_INV  = 0,
                    p_SR_VAL  = 0,
                    i_D       = i[j],
                    i_CLK     = clk,
                    i_EN      = 1,
                    i_SR      = 0,
                    o_Q       = o[j],
                )
            ]

class CologneChipSDROutput:
    @staticmethod
    def lower(dr):
        return CologneChipSDROutputImpl(dr.i, dr.o, dr.clk)
    
# CologneChip SDRTristate ---------------------------------------------------------------------------------

class CologneChipSDRTristateImpl(Module):
    def __init__(self, io, o, oe, i, clk):
        _o    = Signal().like(o)
        _oe_n = Signal().like(oe)
        _i    = Signal().like(i if i is not None else o)
        self.specials += [
            SDROutput(o, _o, clk),
            SDROutput(~oe, _oe_n, clk),
        ]
        if i is not None:
            self.specials += SDRInput(_i, i, clk)
        for j in range(len(io)):
            self.specials += Instance("CC_IOBUF",
                    p_FF_OBF = 1,
                    p_FF_IBF = 1,
                    io_IO = io[j],
                    o_Y   = _i[j],
                    i_A   = _o[j],
                    i_T   = _oe_n[j],
                )

class CologneChipSDRTristate:
    @staticmethod
    def lower(dr):
        return CologneChipSDRTristateImpl(dr.io, dr.o, dr.oe, dr.i, dr.clk)


# CologneChip Tristate -----------------------------------------------------------------------------

class CologneChipTristateImpl(Module):
    def __init__(self, io, o, oe, i):
        nbits, _ = value_bits_sign(io)
        if i is None:
            i = Signal().like(o)
        for bit in range(nbits):
            self.specials += Instance("CC_IOBUF",
                io_IO = io[bit] if nbits > 1 else io,
                o_Y   = i[bit]  if nbits > 1 else i,
                i_A   = o[bit]  if nbits > 1 else o,
                i_T   = ~oe[bit] if len(oe) == nbits > 1 else ~oe,
            )

class CologneChipTristate:
    @staticmethod
    def lower(dr):
        return CologneChipTristateImpl(dr.target, dr.o, dr.oe, dr.i)

# CologneChip Special Overrides --------------------------------------------------------------------

colognechip_special_overrides = {
    AsyncResetSynchronizer: CologneChipAsyncResetSynchronizer,
    DDRInput:               CologneChipDDRInput,
    DDROutput:              CologneChipDDROutput,
    DifferentialInput:      CologneChipDifferentialInput,
    DifferentialOutput:     CologneChipDifferentialOutput,
    SDRInput:               CologneChipSDRInput,
    SDROutput:              CologneChipSDROutput,
    SDRTristate:            CologneChipSDRTristate,
    Tristate:               CologneChipTristate,
}
