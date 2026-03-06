#
# This file is part of LiteX.
#
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2017 William D. Jones <thor0505@comcast.net>
# Copyright (c) 2019 David Shah <dave@ds0.me>
# Copyright (c) 2020 David Corrigan <davidcorrigan714@gmail.com>
# Copyright (c) 2021 Charles-Henri Mousset <ch.mousset@gmail.com>
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
                o_Q  = rst1
            ),
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
        for j in range(len(i)):
            self.specials += Instance("IFS1P3BX",
                i_SCLK = clk,
                i_PD   = 0,
                i_SP   = 1,
                i_D    = i[j],
                o_Q    = o[j],
            )

class LatticeECP5SDRInput:
    @staticmethod
    def lower(dr):
        return LatticeECP5SDRInputImpl(dr.i, dr.o, dr.clk)

# ECP5 SDR Output ----------------------------------------------------------------------------------

class LatticeECP5SDROutputImpl(Module):
    def __init__(self, i, o, clk):
        for j in range(len(o)):
            self.specials += Instance("OFS1P3BX",
                i_SCLK = clk,
                i_PD   = 0,
                i_SP   = 1,
                i_D    = i[j],
                o_Q    = o[j],
            )

class LatticeECP5SDROutput:
    @staticmethod
    def lower(dr):
        return LatticeECP5SDROutputImpl(dr.i, dr.o, dr.clk)

# ECP5 DDR Input -----------------------------------------------------------------------------------

class LatticeECP5DDRInputImpl(Module):
    def __init__(self, i, o1, o2, clk):
        for j in range(len(i)):
            self.specials += Instance("IDDRX1F",
                i_SCLK = clk,
                i_D    = i[j],
                o_Q0   = o1[j],
                o_Q1   = o2[j],
            )

class LatticeECP5DDRInput:
    @staticmethod
    def lower(dr):
        return LatticeECP5DDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)

# ECP5 DDR Output ----------------------------------------------------------------------------------

class LatticeECP5DDROutputImpl(Module):
    def __init__(self, i1, i2, o, clk):
        for j in range(len(o)):
            self.specials += Instance("ODDRX1F",
                i_SCLK = clk,
                i_D0   = i1[j],
                i_D1   = i2[j],
                o_Q    = o[j] ,
            )

class LatticeECP5DDROutput:
    @staticmethod
    def lower(dr):
        return LatticeECP5DDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)

# ECP5 Differential Input --------------------------------------------------------------------------

class LatticeECP5DifferentialInputImpl(Module):
    def __init__(self, i_p, i_n, o):
        self.specials += Instance("ILVDS",
            i_A  = i_p,
            i_AN = i_n,
            o_Z  = o,
        )

class LatticeECP5DifferentialInput:
    @staticmethod
    def lower(dr):
        return LatticeECP5DifferentialInputImpl(dr.i_p, dr.i_n, dr.o)

# ECP5 Differential Output -------------------------------------------------------------------------

class LatticeECP5DifferentialOutputImpl(Module):
    def __init__(self, i, o_p, o_n):
        self.specials += Instance("OLVDS",
            i_A  = i,
            o_Z  = o_p,
            o_ZN = o_n,
        )

class LatticeECP5DifferentialOutput:
    @staticmethod
    def lower(dr):
        return LatticeECP5DifferentialOutputImpl(dr.i, dr.o_p, dr.o_n)

# ECP5 Special Tristate ----------------------------------------------------------------------------

class LatticeECP5TristateImpl(Module):
    def __init__(self, io, o, oe, i):
        nbits, sign = value_bits_sign(io)
        if i is None:
            i = Signal().like(o)
        for bit in range(nbits):
            self.specials += Instance("BB",
                io_B  = io[bit] if nbits > 1 else io,
                i_I   = o[bit]  if nbits > 1 else o,
                o_O   = i[bit]  if nbits > 1 else i,
                i_T   = ~oe[bit] if len(oe) == nbits > 1 else ~oe
            )

class LatticeECP5Tristate(Module):
    @staticmethod
    def lower(dr):
        return LatticeECP5TristateImpl(dr.target, dr.o, dr.oe, dr.i)

# ECP5 Special Overrides ---------------------------------------------------------------------------

lattice_ecp5_special_overrides = {
    AsyncResetSynchronizer: LatticeECP5AsyncResetSynchronizer,
    Tristate:               LatticeECP5Tristate,
    SDRInput:               LatticeECP5SDRInput,
    SDROutput:              LatticeECP5SDROutput,
    DDRInput:               LatticeECP5DDRInput,
    DDROutput:              LatticeECP5DDROutput,
    DifferentialInput:      LatticeECP5DifferentialInput,
    DifferentialOutput:     LatticeECP5DifferentialOutput,
}

# ECP5 Trellis Tristate ----------------------------------------------------------------------------

class LatticeECP5TrellisTristateImpl(Module):
    def __init__(self, io, o, oe, i):
        nbits, sign = value_bits_sign(io)
        if i is None:
            i = Signal().like(o)
        for bit in range(nbits):
            self.specials += Instance("TRELLIS_IO",
                p_DIR = "BIDIR",
                i_B   = io[bit] if nbits > 1 else io,
                i_I   = o[bit]  if nbits > 1 else o,
                o_O   = i[bit]  if nbits > 1 else i,
                i_T   = ~oe[bit] if len(oe) == nbits > 1 else ~oe
            )

class LatticeECP5TrellisTristate(Module):
    @staticmethod
    def lower(dr):
        return LatticeECP5TrellisTristateImpl(dr.target, dr.o, dr.oe, dr.i)

# ECP5 Trellis SDR Tristate ----------------------------------------------------------------------------

class LatticeECP5TrellisSDRTristateImpl(Module):
    def __init__(self, io, o, oe, i, clk):
        _o    = Signal().like(o)
        _oe_n = Signal().like(oe)
        _i    = Signal().like(i if i is not None else o)
        self.specials += SDROutput(o, _o, clk)
        self.specials += SDROutput(~oe, _oe_n, clk)
        if i is not None:
            self.specials += SDRInput(_i, i, clk)
        for j in range(len(io)):
            self.specials += Instance("TRELLIS_IO",
                p_DIR = "BIDIR",
                i_B   = io[j],
                i_I   = _o[j],
                o_O   = _i[j],
                i_T   = _oe_n[j],
            )

class LatticeECP5TrellisSDRTristate:
    @staticmethod
    def lower(dr):
        return LatticeECP5TrellisSDRTristateImpl(dr.io, dr.o, dr.oe, dr.i, dr.clk)


# ECP5 Trellis Special Overrides -------------------------------------------------------------------

lattice_ecp5_trellis_special_overrides = {
    AsyncResetSynchronizer: LatticeECP5AsyncResetSynchronizer,
    Tristate:               LatticeECP5TrellisTristate,
    SDRInput:               LatticeECP5SDRInput,
    SDROutput:              LatticeECP5SDROutput,
    SDRTristate:            LatticeECP5TrellisSDRTristate,
    DDRInput:               LatticeECP5DDRInput,
    DDROutput:              LatticeECP5DDROutput,
    DifferentialInput:      LatticeECP5DifferentialInput,
    DifferentialOutput:     LatticeECP5DifferentialOutput,
}


# NX AsyncResetSynchronizer ------------------------------------------------------------------------

class LatticeNXsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst1 = Signal()
        self.specials += [
            Instance("FD1P3BX",
                i_D  = 0,
                i_PD = async_reset,
                i_CK = cd.clk,
                i_SP = 1,
                o_Q  = rst1
            ),
            Instance("FD1P3BX",
                i_D  = rst1,
                i_PD = async_reset,
                i_CK = cd.clk,
                i_SP = 1,
                o_Q  = cd.rst)
        ]


class LatticeNXAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return LatticeNXsyncResetSynchronizerImpl(dr.cd, dr.async_reset)


# NX SDR Input -------------------------------------------------------------------------------------

class LatticeNXSDRInputImpl(Module):
    def __init__(self, i, o, clk):
        for j in range(len(i)):
            self.specials += Instance("IFD1P3BX",
                i_CK = clk,
                i_PD   = 0,
                i_SP   = 1,
                i_D    = i[j],
                o_Q    = o[j],
            )

class LatticeNXSDRInput:
    @staticmethod
    def lower(dr):
        return LatticeNXSDRInputImpl(dr.i, dr.o, dr.clk)

# NX SDR Output ------------------------------------------------------------------------------------

class LatticeNXSDROutputImpl(Module):
    def __init__(self, i, o, clk):
        for j in range(len(o)):
            self.specials += Instance("OFD1P3BX",
                i_CK = clk,
                i_PD   = 0,
                i_SP   = 1,
                i_D    = i[j],
                o_Q    = o[j],
            )

class LatticeNXSDROutput:
    @staticmethod
    def lower(dr):
        return LatticeNXSDROutputImpl(dr.i, dr.o, dr.clk)

# NX SDR Input and Output via regular flip-flops ---------------------------------------------------

# This is a workaround for IO-specific primitives IFD1P3BX / OFD1P3BX being unsupported in nextpnr:
# https://github.com/YosysHQ/nextpnr/issues/698

class LatticeNXSDRFFImpl(Module):
    def __init__(self, i, o, clk):
        for j in range(len(o)):
            self.specials += Instance("FD1P3BX",
                i_CK = clk,
                i_PD   = 0,
                i_SP   = 1,
                i_D    = i[j],
                o_Q    = o[j],
            )

class LatticeNXSDRInputViaFlipFlop:
    @staticmethod
    def lower(dr):
        return LatticeNXSDRFFImpl(dr.i, dr.o, dr.clk)

class LatticeNXSDROutputViaFlipFlop:
    @staticmethod
    def lower(dr):
        return LatticeNXSDRFFImpl(dr.i, dr.o, dr.clk)

# NX DDR Input -------------------------------------------------------------------------------------

class LatticeNXDDRInputImpl(Module):
    def __init__(self, i, o1, o2, clk):
        for j in range(len(i)):
            self.specials += Instance("IDDRX1",
                i_SCLK = clk,
                i_D    = i[j],
                o_Q0   = o1[j],
                o_Q1   = o2[j],
            )

class LatticeNXDDRInput:
    @staticmethod
    def lower(dr):
        return LatticeNXDDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)

# NX DDR Output ------------------------------------------------------------------------------------

class LatticeNXDDROutputImpl(Module):
    def __init__(self, i1, i2, o, clk):
        for j in range(len(o)):
            self.specials += Instance("ODDRX1",
                i_SCLK = clk,
                i_D0   = i1[j],
                i_D1   = i2[j],
                o_Q    = o[j] ,
            )

class LatticeNXDDROutput:
    @staticmethod
    def lower(dr):
        return LatticeNXDDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)

# NX DDR Tristate ----------------------------------------------------------------------------------

class LatticeNXDDRTristateImpl(Module):
    def __init__(self, io, o1, o2, oe1, oe2, i1, i2, clk):
        assert oe2 is None
        _o  = Signal().like(o1)
        _oe = Signal().like(oe1)
        _i  = Signal().like(_o) if i1 is not None and i2 is not None else None
        self.specials += DDROutput(o1, o2, _o, clk)
        self.specials += SDROutput(oe1, _oe, clk)
        if _i is not None:
            self.specials += DDRInput(_i, i1, i2, clk)
        self.specials += Tristate(io, _o, _oe, _i)
        _oe.attr.add("syn_useioff")

class LatticeNXDDRTristate:
    @staticmethod
    def lower(dr):
        return LatticeNXDDRTristateImpl(dr.io, dr.o1, dr.o2, dr.oe1, dr.oe2, dr.i1, dr.i2, dr.clk)

# NX Special Overrides -----------------------------------------------------------------------------

lattice_NX_special_overrides = {
    AsyncResetSynchronizer: LatticeNXAsyncResetSynchronizer,
    SDRInput:               LatticeNXSDRInput,
    SDROutput:              LatticeNXSDROutput,
    DDRInput:               LatticeNXDDRInput,
    DDROutput:              LatticeNXDDROutput,
    DDRTristate:            LatticeNXDDRTristate,
}

lattice_NX_special_overrides_for_oxide = dict(lattice_NX_special_overrides)
lattice_NX_special_overrides_for_oxide.update({
    SDRInput:               LatticeNXSDRInputViaFlipFlop,
    SDROutput:              LatticeNXSDROutputViaFlipFlop,
})

# iCE40 AsyncResetSynchronizer ---------------------------------------------------------------------

class LatticeiCE40AsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst1 = Signal()
        self.specials += [
            Instance("SB_DFFS",
                i_D = 0,
                i_S = async_reset,
                i_C = cd.clk,
                o_Q = rst1
            ),
            Instance("SB_DFFS",
                i_D = rst1,
                i_S = async_reset,
                i_C = cd.clk,
                o_Q = cd.rst
            )
        ]


class LatticeiCE40AsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return LatticeiCE40AsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

# iCE40 Tristate -----------------------------------------------------------------------------------

class LatticeiCE40TristateImpl(Module):
    def __init__(self, io, o, oe, i):
        nbits, sign = value_bits_sign(io)
        if i is None:
            i = Signal().like(o)
        for bit in range(nbits):
            self.specials += Instance("SB_IO",
                p_PIN_TYPE      = C(0b101001, 6), # PIN_OUTPUT_TRISTATE + PIN_INPUT
                io_PACKAGE_PIN  = io[bit] if nbits > 1 else io,
                i_OUTPUT_ENABLE = oe[bit] if len(oe) == nbits > 1 else oe,
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

# iCE40 Differential Input -------------------------------------------------------------------------

class LatticeiCE40DifferentialInputImpl(Module):
    def __init__(self, i_p, o):
        self.specials += [
            Instance("SB_IO",
                p_PIN_TYPE     = C(0b000001, 6), # PIN_INPUT
                p_IO_STANDARD  = "SB_LVDS_INPUT",
                p_PULLUP       = C(0b0, 1),
                p_NEG_TRIGGER  = C(0b0, 1),
                io_PACKAGE_PIN = i_p,
                o_D_IN_0       = o,
                i_OUTPUT_ENABLE= C(0b1, 1)
            ),
            # according to https://www.latticesemi.com/support/answerdatabase/6/1/6/6161 the n pin
            # will get assigned to the LVDS input automatically
        ]

class LatticeiCE40DifferentialInput:
    @staticmethod
    def lower(dr):
        return LatticeiCE40DifferentialInputImpl(dr.i_p, dr.o)

# iCE40 DDR Output ---------------------------------------------------------------------------------

class LatticeiCE40DDROutputImpl(Module):
    def __init__(self, i1, i2, o, clk):
        for j in range(len(o)):
            self.specials += Instance("SB_IO",
                p_PIN_TYPE      = C(0b010000, 6), # PIN_OUTPUT_DDR
                p_IO_STANDARD   = "SB_LVCMOS",
                io_PACKAGE_PIN  = o[j],
                i_CLOCK_ENABLE  = 1,
                i_OUTPUT_CLK    = clk,
                i_OUTPUT_ENABLE = 1,
                i_D_OUT_0       = i1[j],
                i_D_OUT_1       = i2[j]
            )


class LatticeiCE40DDROutput:
    @staticmethod
    def lower(dr):
        return LatticeiCE40DDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)

# iCE40 DDR Input ----------------------------------------------------------------------------------

class LatticeiCE40DDRInputImpl(Module):
    def __init__(self, i, o1, o2, clk):
        for j in range(len(i)):
            self.specials += Instance("SB_IO",
                p_PIN_TYPE      = C(0b000000, 6),  # PIN_INPUT_DDR
                p_IO_STANDARD   = "SB_LVCMOS",
                io_PACKAGE_PIN  = i[j],
                i_CLOCK_ENABLE  = 1,
                i_INPUT_CLK     = clk,
                o_D_IN_0        = o1[j],
                o_D_IN_1        = o2[j]
            )


class LatticeiCE40DDRInput:
    @staticmethod
    def lower(dr):
        return LatticeiCE40DDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)

# iCE40 SDR Output ---------------------------------------------------------------------------------

class LatticeiCE40SDROutputImpl(Module):
    def __init__(self, i, o, clk):
        for j in range(len(o)):
            self.specials += Instance("SB_IO",
                # i_INPUT_CLK must match between two SB_IOs in the same tile.
                # In PIN_INPUT mode, this restriction is relaxed; an unconnected
                # i_INPUT_CLK also works.
                p_PIN_TYPE      = C(0b010101, 6), # PIN_OUTPUT_REGISTERED + PIN_INPUT
                p_IO_STANDARD   = "SB_LVCMOS",
                io_PACKAGE_PIN  = o[j],
                i_CLOCK_ENABLE  = 1,
                i_OUTPUT_CLK    = clk,
                i_OUTPUT_ENABLE = 1,
                i_D_OUT_0       = i[j]
            )

class LatticeiCE40SDROutput:
    @staticmethod
    def lower(dr):
        return LatticeiCE40SDROutputImpl(dr.i, dr.o, dr.clk)

# iCE40 SDR Input ----------------------------------------------------------------------------------

class LatticeiCE40SDRInput:
    @staticmethod
    def lower(dr):
        return LatticeiCE40DDRInputImpl(dr.i, dr.o, Signal(len(dr.o)), dr.clk)

# iCE40 SDR Tristate -------------------------------------------------------------------------------

class LatticeiCE40SDRTristateImpl(Module):
    def __init__(self, io, o, oe, i, clk):
        if i is None:
            i = Signal().like(o)
        for j in range(len(io)):
            self.specials += Instance("SB_IO",
                p_PIN_TYPE      = C(0b110100, 6), # PIN_OUTPUT_REGISTERED_ENABLE_REGISTERED + PIN_INPUT_REGISTERED
                io_PACKAGE_PIN  = io[j],
                i_INPUT_CLK     = clk,
                i_OUTPUT_CLK    = clk,
                i_OUTPUT_ENABLE = oe[j],
                i_D_OUT_0       = o[j] ,
                o_D_IN_0        = i[j] ,
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
    DifferentialInput:      LatticeiCE40DifferentialInput,
    DDROutput:              LatticeiCE40DDROutput,
    DDRInput:               LatticeiCE40DDRInput,
    SDROutput:              LatticeiCE40SDROutput,
    SDRInput:               LatticeiCE40SDRInput,
    SDRTristate:            LatticeiCE40SDRTristate,
}
