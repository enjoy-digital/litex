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

# Gowin Special Overrides --------------------------------------------------------------------------

gowin_special_overrides = {
    AsyncResetSynchronizer: GowinAsyncResetSynchronizer,
    DDRInput:               GowinDDRInput,
    DDROutput:              GowinDDROutput,
    DifferentialInput:      GowinDifferentialInput,
    DifferentialOutput:     GowinDifferentialOutput,
}

# Gw5A Tristate ------------------------------------------------------------------------------------

class Gw5ATristateImpl(Module):
    def __init__(self, io, o, oe, i):
        nbits, _ = value_bits_sign(io)
        if i is None:
            i = Signal().like(o)
        for bit in range(nbits):
            self.specials += Instance("IOBUF",
                io_IO = io[bit] if nbits > 1 else io,
                o_O   = i[bit]  if nbits > 1 else i,
                i_I   = o[bit]  if nbits > 1 else o,
                i_OEN = ~oe[bit] if len(oe) == nbits > 1 else ~oe,
            )

class Gw5ATristate:
    @staticmethod
    def lower(dr):
        return Gw5ATristateImpl(dr.target, dr.o, dr.oe, dr.i)

# Gw5A SDROutput -----------------------------------------------------------------------------------

class Gw5ASDROutputImpl(Module):
    def __init__(self, i, o, clk):
        for j in range(len(o)):
            self.specials += Instance("DFFSE",
                    i_D   = i[j],
                    o_Q   = o[j],
                    i_CLK = clk,
                    i_SET = Constant(0,1),
                    i_CE  = Constant(1,1),
            )

class Gw5ASDROutput:
    @staticmethod
    def lower(dr):
        return Gw5ASDROutputImpl(dr.i, dr.o, dr.clk)

# Gw5A SDRInput ------------------------------------------------------------------------------------

class Gw5ASDRInputImpl(Module):
    def __init__(self, i, o, clk):
        for j in range(len(i)):
            self.specials += Instance("DFFSE",
                    i_D   = i[j],
                    o_Q   = o[j],
                    i_CLK = clk,
                    i_SET = Constant(0,1),
                    i_CE  = Constant(1,1),
            )

class Gw5ASDRInput:
    @staticmethod
    def lower(dr):
        return Gw5ASDRInputImpl(dr.i, dr.o, dr.clk)

# Gw5A SDRTristate ---------------------------------------------------------------------------------

class Gw5ASDRTristateImpl(Module):
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
            self.specials += Instance("IOBUF",
                    io_IO = io[j],
                    o_O   = _i[j],
                    i_I   = _o[j],
                    i_OEN = _oe_n[j],
                )
        

class Gw5ASDRTristate:
    @staticmethod
    def lower(dr):
        return Gw5ASDRTristateImpl(dr.io, dr.o, dr.oe, dr.i, dr.clk)

# Gw5A Special Overrides ---------------------------------------------------------------------------

gw5a_special_overrides = {
    SDRTristate: Gw5ASDRTristate,
    SDROutput:   Gw5ASDROutput,
    SDRInput:    Gw5ASDRInput,
    Tristate:    Gw5ATristate,
}
