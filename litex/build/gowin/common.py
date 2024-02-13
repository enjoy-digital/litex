#
# This file is part of LiteX.
#
# Copyright (c) 2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen.fhdl.module import Module
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen import *

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
                o_Q      = rst1
            ),
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

# Gowin DDR Input ----------------------------------------------------------------------------------

class GowinDDRInputImpl(Module):
    def __init__(self, i, o1, o2, clk):
        self.specials += Instance("IDDR",
            i_CLK = clk,
            i_D   = i,
            o_Q0  = o1,
            o_Q1  = o2,
        )

class GowinDDRInput:
    @staticmethod
    def lower(dr):
        return GowinDDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)

# Gowin DDR Output ---------------------------------------------------------------------------------

class GowinDDROutputImpl(Module):
    def __init__(self, i1, i2, o, clk):
        self.specials += Instance("ODDR",
            i_CLK = clk,
            i_D0  = i1,
            i_D1  = i2,
            i_TX  = 0,
            o_Q0  = o,
            o_Q1  = Open(),
        )

class GowinDDROutput:
    @staticmethod
    def lower(dr):
        return GowinDDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)

# Gowin Differential Input -------------------------------------------------------------------------

class GowinDifferentialInputImpl(Module):
    def __init__(self, i_p, i_n, o):
        self.specials += Instance("TLVDS_IBUF",
            i_I  = i_p,
            i_IB = i_n,
            o_O  = o,
        )

class GowinDifferentialInput:
    @staticmethod
    def lower(dr):
        return GowinDifferentialInputImpl(dr.i_p, dr.i_n, dr.o)

# Gowin Differential Output ------------------------------------------------------------------------

class GowinDifferentialOutputImpl(Module):
    def __init__(self, i, o_p, o_n):
        self.specials += Instance("TLVDS_OBUF",
            i_I  = i,
            o_O  = o_p,
            o_OB = o_n,
        )

class GowinDifferentialOutput:
    @staticmethod
    def lower(dr):
        return GowinDifferentialOutputImpl(dr.i, dr.o_p, dr.o_n)

# Gowin Tristate -----------------------------------------------------------------------------------

class GowinTristateImpl(Module):
    def __init__(self, io, o, oe, i):
        nbits, _ = value_bits_sign(io)
        for bit in range(nbits):
            self.specials += Instance("IOBUF",
                io_IO = io[bit] if nbits > 1 else io,
                o_O   = i[bit]  if nbits > 1 else i,
                i_I   = o[bit]  if nbits > 1 else o,
                i_OEN = ~oe,
            )

class GowinTristate:
    @staticmethod
    def lower(dr):
        return GowinTristateImpl(dr.target, dr.o, dr.oe, dr.i)

# Gowin Special Overrides --------------------------------------------------------------------------

gowin_special_overrides = {
    AsyncResetSynchronizer: GowinAsyncResetSynchronizer,
    DDRInput:               GowinDDRInput,
    DDROutput:              GowinDDROutput,
    DifferentialInput:      GowinDifferentialInput,
    DifferentialOutput:     GowinDifferentialOutput,
    #Tristate:               GowinTristate, # FIXME: issue with tangNano9k hyperram
}
