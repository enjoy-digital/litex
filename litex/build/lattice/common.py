# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2017 William D. Jones <thor0505@comcast.net>
# This file is Copyright (c) 2019 David Shah <dave@ds0.me>
# License: BSD

from migen.fhdl.module import Module
from migen.fhdl.specials import Instance, Tristate
from migen.fhdl.bitcontainer import value_bits_sign
from migen.genlib.io import *
from migen.genlib.resetsync import AsyncResetSynchronizer

# ECPX AsyncResetSynchronizer ----------------------------------------------------------------------

class LatticeECPXAsyncResetSynchronizerImpl(Module):
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


class LatticeECPXAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return LatticeECPXAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

# ECPX Differential Output -------------------------------------------------------------------------

class LatticeECPXDDROutputImpl(Module):
    def __init__(self, i1, i2, o, clk):
        self.specials += [
            Instance("ODDRXD1",
                synthesis_directive="ODDRAPPS=\"SCLK_ALIGNED\"",
                i_SCLK = clk,
                i_DA   = i1,
                i_DB   = i2,
                o_Q    = o)
        ]


class LatticeECPXDDROutput:
    @staticmethod
    def lower(dr):
        return LatticeECPXDDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)

# ECPX Special Overrides ---------------------------------------------------------------------------

lattice_ecpx_special_overrides = {
    AsyncResetSynchronizer: LatticeECPXAsyncResetSynchronizer,
    DDROutput:              LatticeECPXDDROutput
}

# ECPX Trellis Tristate ----------------------------------------------------------------------------

class LatticeECPXTrellisTristateImpl(Module):
    def __init__(self, io, o, oe, i):
        nbits, sign = value_bits_sign(io)
        if nbits == 1:
            self.specials += [
              Instance("TRELLIS_IO",
                    p_DIR = "BIDIR",
                    i_B   = io,
                    i_I   = o,
                    o_O   = i,
                    i_T   = ~oe
                )
            ]
        else:
            for bit in range(nbits):
                self.specials += [
                    Instance("TRELLIS_IO",
                        p_DIR="BIDIR",
                        i_B = io[bit],
                        i_I = o[bit],
                        o_O = i[bit],
                        i_T = ~oe
                    )
                ]


class LatticeECPXTrellisTristate(Module):
    @staticmethod
    def lower(dr):
        return LatticeECPXTrellisTristateImpl(dr.target, dr.o, dr.oe, dr.i)

# ECPX Trellis Special Overrides -------------------------------------------------------------------

lattice_ecpx_trellis_special_overrides = {
    AsyncResetSynchronizer: LatticeECPXAsyncResetSynchronizer,
    Tristate:               LatticeECPXTrellisTristate,
    DDROutput:              LatticeECPXDDROutput
}

# iCE40 AsyncResetSynchronizer ----------------------------------------------------------------------

class LatticeiCE40AsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst1 = Signal()
        self.specials += [
            Instance("SB_DFFS", i_D=0, i_S=async_reset,
                     i_C=cd.clk, o_Q=rst1),
            Instance("SB_DFFS", i_D=rst1, i_S=async_reset,
                     i_C=cd.clk, o_Q=cd.rst)
        ]


class LatticeiCE40AsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return LatticeiCE40AsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

# iCE40 Trellis Tristate ---------------------------------------------------------------------------

class LatticeiCE40TristateImpl(Module):
    def __init__(self, io, o, oe, i):
        nbits, sign = value_bits_sign(io)
        if nbits == 1:
            self.specials +=  [
                Instance("SB_IO",
                    p_PIN_TYPE      = C(0b101001, 6),
                    io_PACKAGE_PIN  = io,
                    i_OUTPUT_ENABLE = oe,
                    i_D_OUT_0       = o,
                    o_D_IN_0        = i
                )
            ]
        else:
            for bit in range(nbits):
                self.specials += [
                    Instance("SB_IO",
                        p_PIN_TYPE      = C(0b101001, 6),
                        io_PACKAGE_PIN  = io[bit],
                        i_OUTPUT_ENABLE = oe,
                        i_D_OUT_0       = o[bit],
                        o_D_IN_0        = i[bit]
                    )
                ]


class LatticeiCE40Tristate(Module):
    @staticmethod
    def lower(dr):
        return LatticeiCE40TristateImpl(dr.target, dr.o, dr.oe, dr.i)

# iCE40 Differential Output ------------------------------------------------------------------------

class LatticeiCE40DifferentialOutputImpl(Module):
    def __init__(self, i, o_p, o_n):
        self.specials += [
            Instance("SB_IO",
                p_PIN_TYPE     = C(0b011000, 6),
                p_IO_STANDARD  = "SB_LVCMOS",
                io_PACKAGE_PIN = o_p,
                i_D_OUT_0      = i
            )
        ]

        self.specials += [
            Instance("SB_IO",
                p_PIN_TYPE     = C(0b011000, 6),
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
        self.specials += [
            Instance("SB_IO",
                p_PIN_TYPE      = C(0b010000, 6),
                p_IO_STANDARD   = "SB_LVCMOS",
                io_PACKAGE_PIN  = o,
                i_CLOCK_ENABLE  = 1,
                i_OUTPUT_CLK    = clk,
                i_OUTPUT_ENABLE = 1,
                i_D_OUT_0       = i1,
                i_D_OUT_1       = i2
            )
        ]


class LatticeiCE40DDROutput:
    @staticmethod
    def lower(dr):
        return LatticeiCE40DDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)

# iCE40 Trellis Special Overrides ------------------------------------------------------------------

lattice_ice40_special_overrides = {
    AsyncResetSynchronizer: LatticeiCE40AsyncResetSynchronizer,
    Tristate:               LatticeiCE40Tristate,
    DifferentialOutput:     LatticeiCE40DifferentialOutput,
    DDROutput:              LatticeiCE40DDROutput
}
