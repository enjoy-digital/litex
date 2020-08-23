#
# This file is part of LiteX.
#
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2017 William D. Jones <thor0505@comcast.net>
# Copyright (c) 2019 David Shah <dave@ds0.me>
# SPDX-License-Identifier: BSD-2-Clause

from migen.fhdl.module import Module
from migen.fhdl.specials import Instance, Tristate
from migen.fhdl.bitcontainer import value_bits_sign
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import *

# ECP5 AsyncResetSynchronizer ----------------------------------------------------------------------

class LatticeECP5AsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst1 = Signal()
        self.specials += [
            Instance("FD1S3BX",
                i_D  = 0,
                i_PD = async_reset,
                i_CK = cd.clk,
                o_Q  = rst1),
            Instance("FD1S3BX",
                i_D  = rst1,
                i_PD = async_reset,
                i_CK = cd.clk,
                o_Q  = cd.rst)
        ]


class LatticeECP5AsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return LatticeECP5AsyncResetSynchronizerImpl(dr.cd, dr.async_reset)


# ECP5 SDR Input -----------------------------------------------------------------------------------

class LatticeECP5SDRInputImpl(Module):
    def __init__(self, i, o, clk):
        self.specials += Instance("IFS1P3BX",
            i_SCLK = clk,
            i_PD   = 0,
            i_SP   = 1,
            i_D    = i,
            o_Q    = o,
        )

class LatticeECP5SDRInput:
    @staticmethod
    def lower(dr):
        return LatticeECP5SDRInputImpl(dr.i, dr.o, dr.clk)

# ECP5 SDR Output ----------------------------------------------------------------------------------

class LatticeECP5SDROutputImpl(Module):
    def __init__(self, i, o, clk):
        self.specials += Instance("OFS1P3BX",
            i_SCLK = clk,
            i_PD   = 0,
            i_SP   = 1,
            i_D    = i,
            o_Q    = o,
        )

class LatticeECP5SDROutput:
    @staticmethod
    def lower(dr):
        return LatticeECP5SDROutputImpl(dr.i, dr.o, dr.clk)

# ECP5 DDR Input -----------------------------------------------------------------------------------

class LatticeECP5DDRInputImpl(Module):
    def __init__(self, i, o1, o2, clk):
        self.specials += Instance("IDDRX1F",
            i_SCLK = clk,
            i_D    = i,
            o_Q0   = o1,
            o_Q1   = o2,
        )

class LatticeECP5DDRInput:
    @staticmethod
    def lower(dr):
        return LatticeECP5DDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)

# ECP5 DDR Output ----------------------------------------------------------------------------------

class LatticeECP5DDROutputImpl(Module):
    def __init__(self, i1, i2, o, clk):
        self.specials += Instance("ODDRX1F",
            i_SCLK = clk,
            i_D0   = i1,
            i_D1   = i2,
            o_Q    = o,
        )

class LatticeECP5DDROutput:
    @staticmethod
    def lower(dr):
        return LatticeECP5DDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)

# ECP5 Special Overrides ---------------------------------------------------------------------------

lattice_ecp5_special_overrides = {
    AsyncResetSynchronizer: LatticeECP5AsyncResetSynchronizer,
    SDRInput:               LatticeECP5SDRInput,
    SDROutput:              LatticeECP5SDROutput,
    DDRInput:               LatticeECP5DDRInput,
    DDROutput:              LatticeECP5DDROutput,
}

# ECP5 Trellis Tristate ----------------------------------------------------------------------------

class LatticeECP5TrellisTristateImpl(Module):
    def __init__(self, io, o, oe, i):
        nbits, sign = value_bits_sign(io)
        for bit in range(nbits):
            self.specials += Instance("TRELLIS_IO",
                p_DIR = "BIDIR",
                i_B   = io[bit] if nbits > 1 else io,
                i_I   = o[bit]  if nbits > 1 else o,
                o_O   = i[bit]  if nbits > 1 else i,
                i_T   = ~oe
            )

class LatticeECP5TrellisTristate(Module):
    @staticmethod
    def lower(dr):
        return LatticeECP5TrellisTristateImpl(dr.target, dr.o, dr.oe, dr.i)

# ECP5 Trellis Special Overrides -------------------------------------------------------------------

lattice_ecp5_trellis_special_overrides = {
    AsyncResetSynchronizer: LatticeECP5AsyncResetSynchronizer,
    Tristate:               LatticeECP5TrellisTristate,
    SDRInput:               LatticeECP5SDRInput,
    SDROutput:              LatticeECP5SDROutput,
    DDRInput:               LatticeECP5DDRInput,
    DDROutput:              LatticeECP5DDROutput
}

# iCE40 AsyncResetSynchronizer ----------------------------------------------------------------------

class LatticeiCE40AsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst1 = Signal()
        self.specials += [
            Instance("SB_DFFS",
                i_D = 0,
                i_S = async_reset,
                i_C = cd.clk,
                o_Q = rst1),
            Instance("SB_DFFS",
                i_D = rst1,
                i_S = async_reset,
                i_C = cd.clk,
                o_Q = cd.rst)
        ]


class LatticeiCE40AsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return LatticeiCE40AsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

# iCE40 Tristate -----------------------------------------------------------------------------------

class LatticeiCE40TristateImpl(Module):
    def __init__(self, io, o, oe, i):
        nbits, sign = value_bits_sign(io)
        for bit in range(nbits):
            self.specials += Instance("SB_IO",
                p_PIN_TYPE      = C(0b101001, 6), # PIN_OUTPUT_TRISTATE + PIN_INPUT
                io_PACKAGE_PIN  = io[bit] if nbits > 1 else io,
                i_OUTPUT_ENABLE = oe,
                i_D_OUT_0       = o[bit]  if nbits > 1 else o,
                o_D_IN_0        = i[bit]  if nbits > 1 else i,
            )

class LatticeiCE40Tristate(Module):
    @staticmethod
    def lower(dr):
        return LatticeiCE40TristateImpl(dr.target, dr.o, dr.oe, dr.i)

# iCE40 Differential Output ------------------------------------------------------------------------

class LatticeiCE40DifferentialOutputImpl(Module):
    def __init__(self, i, o_p, o_n):
        self.specials += [
            Instance("SB_IO",
                p_PIN_TYPE     = C(0b011000, 6), # PIN_OUTPUT
                p_IO_STANDARD  = "SB_LVCMOS",
                io_PACKAGE_PIN = o_p,
                i_D_OUT_0      = i
            ),
            Instance("SB_IO",
                p_PIN_TYPE     = C(0b011000, 6), # PIN_OUTPUT
                p_IO_STANDARD  = "SB_LVCMOS",
                io_PACKAGE_PIN = o_n,
                i_D_OUT_0      = ~i
            )
        ]

class LatticeiCE40DifferentialOutput:
    @staticmethod
    def lower(dr):
        return LatticeiCE40DifferentialOutputImpl(dr.i, dr.o_p, dr.o_n)

# iCE40 DDR Output ---------------------------------------------------------------------------------

class LatticeiCE40DDROutputImpl(Module):
    def __init__(self, i1, i2, o, clk):
        self.specials += Instance("SB_IO",
            p_PIN_TYPE      = C(0b010000, 6), # PIN_OUTPUT_DDR
            p_IO_STANDARD   = "SB_LVCMOS",
            io_PACKAGE_PIN  = o,
            i_CLOCK_ENABLE  = 1,
            i_OUTPUT_CLK    = clk,
            i_OUTPUT_ENABLE = 1,
            i_D_OUT_0       = i1,
            i_D_OUT_1       = i2
        )


class LatticeiCE40DDROutput:
    @staticmethod
    def lower(dr):
        return LatticeiCE40DDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)

# iCE40 DDR Input ----------------------------------------------------------------------------------

class LatticeiCE40DDRInputImpl(Module):
    def __init__(self, i, o1, o2, clk):
        self.specials += Instance("SB_IO",
            p_PIN_TYPE      = C(0b000000, 6),  # PIN_INPUT_DDR
            p_IO_STANDARD   = "SB_LVCMOS",
            io_PACKAGE_PIN  = i,
            i_CLOCK_ENABLE  = 1,
            i_INPUT_CLK     = clk,
            o_D_IN_0        = o1,
            o_D_IN_1        = o2
        )


class LatticeiCE40DDRInput:
    @staticmethod
    def lower(dr):
        return LatticeiCE40DDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)

# iCE40 SDR Output ---------------------------------------------------------------------------------

class LatticeiCE40SDROutputImpl(Module):
    def __init__(self, i, o, clk):
        self.specials += Instance("SB_IO",
            p_PIN_TYPE      = C(0b010100, 6), # PIN_OUTPUT_REGISTERED
            p_IO_STANDARD   = "SB_LVCMOS",
            io_PACKAGE_PIN  = o,
            i_CLOCK_ENABLE  = 1,
            i_OUTPUT_CLK    = clk,
            i_OUTPUT_ENABLE = 1,
            i_D_OUT_0       = i
        )

class LatticeiCE40SDROutput:
    @staticmethod
    def lower(dr):
        return LatticeiCE40SDROutputImpl(dr.i, dr.o, dr.clk)

# iCE40 SDR Input ----------------------------------------------------------------------------------

class LatticeiCE40SDRInput:
    @staticmethod
    def lower(dr):
        return LatticeiCE40DDRInputImpl(dr.i, dr.o, Signal(), dr.clk)

# iCE40 SDR Tristate -------------------------------------------------------------------------------

class LatticeiCE40SDRTristateImpl(Module):
    def __init__(self, io, o, oe, i, clk):
        self.specials += Instance("SB_IO",
            p_PIN_TYPE      = C(0b110100, 6), # PIN_OUTPUT_REGISTERED_ENABLE_REGISTERED + PIN_INPUT_REGISTERED
            io_PACKAGE_PIN  = io,
            i_INPUT_CLK     = clk,
            i_OUTPUT_CLK    = clk,
            i_OUTPUT_ENABLE = oe,
            i_D_OUT_0       = o,
            o_D_IN_0        = i,
        )

class LatticeiCE40SDRTristate(Module):
    @staticmethod
    def lower(dr):
        return LatticeiCE40SDRTristateImpl(dr.io, dr.o, dr.oe, dr.i, dr.clk)

# iCE40 Trellis Special Overrides ------------------------------------------------------------------

lattice_ice40_special_overrides = {
    AsyncResetSynchronizer: LatticeiCE40AsyncResetSynchronizer,
    Tristate:               LatticeiCE40Tristate,
    DifferentialOutput:     LatticeiCE40DifferentialOutput,
    DDROutput:              LatticeiCE40DDROutput,
    DDRInput:               LatticeiCE40DDRInput,
    SDROutput:              LatticeiCE40SDROutput,
    SDRInput:               LatticeiCE40SDRInput,
    SDRTristate:            LatticeiCE40SDRTristate,
}
