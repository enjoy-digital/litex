#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 vytautasb <v.buitvydas@limemicro.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.fhdl.module import Module
from migen.fhdl.specials import Instance
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import *

# Common JTAG --------------------------------------------------------------------------------------

altera_reserved_jtag_pads = [
    "altera_reserved_tms",
    "altera_reserved_tck",
    "altera_reserved_tdi",
    "altera_reserved_tdo",
]

# Common AsyncResetSynchronizer --------------------------------------------------------------------

class AlteraAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst_meta = Signal(name_override=f'ars_cd_{cd.name}_rst_meta')
        self.specials += [
            Instance("DFF", name=f'ars_cd_{cd.name}_ff0',
                i_d    = 0,
                i_clk  = cd.clk,
                i_clrn = 1,
                i_prn  = ~async_reset,
                o_q    = rst_meta
            ),
            Instance("DFF", name=f'ars_cd_{cd.name}_ff1',
                i_d    = rst_meta,
                i_clk  = cd.clk,
                i_clrn = 1,
                i_prn  = ~async_reset,
                o_q    = cd.rst
            )
        ]


class AlteraAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return AlteraAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

# Common DifferentialInput -------------------------------------------------------------------------

class AlteraDifferentialInputImpl(Module):
    def __init__(self, i_p, i_n, o):
        self.specials += [
            Instance("ALT_INBUF_DIFF",
                name   = "ibuf_diff",
                i_i    = i_p,
                i_ibar = i_n,
                o_o    = o
            )
        ]


class AlteraDifferentialInput:
    @staticmethod
    def lower(dr):
        return AlteraDifferentialInputImpl(dr.i_p, dr.i_n, dr.o)

# Common DifferentialOutput ------------------------------------------------------------------------

class AlteraDifferentialOutputImpl(Module):
    def __init__(self, i, o_p, o_n):
        self.specials += [
            Instance("ALT_OUTBUF_DIFF",
                name   = "obuf_diff",
                i_i    = i,
                o_o    = o_p,
                o_obar = o_n
            )
        ]


class AlteraDifferentialOutput:
    @staticmethod
    def lower(dr):
        return AlteraDifferentialOutputImpl(dr.i, dr.o_p, dr.o_n)

# Common DDROutput ---------------------------------------------------------------------------------

class AlteraDDROutputImpl(Module):
    def __init__(self, i1, i2, o, clk):
        for j in range(len(o)):
            self.specials += Instance("ALTDDIO_OUT",
                p_WIDTH    = 1,
                i_outclock = clk,
                i_datain_h = i1[j],
                i_datain_l = i2[j],
                o_dataout  = o[j],
            )

class AlteraDDROutput:
    @staticmethod
    def lower(dr):
        return AlteraDDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)

# Common DDRInput ----------------------------------------------------------------------------------

class AlteraDDRInputImpl(Module):
    def __init__(self, i, o1, o2, clk):
        for j in range(len(i)):
            self.specials += Instance("ALTDDIO_IN",
                p_WIDTH     = 1,
                i_inclock   = clk,
                i_datain    = i[j],
                o_dataout_h = o1[j],
                o_dataout_l = o2[j],
            )

class AlteraDDRInput:
    @staticmethod
    def lower(dr):
        return AlteraDDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)

# Common SDROutput -------------------------------------------------------------------------------

class AlteraSDROutput:
    @staticmethod
    def lower(dr):
        return AlteraDDROutputImpl(dr.i, dr.i, dr.o, dr.clk)

# Common SDRInput --------------------------------------------------------------------------------

class AlteraSDRInput:
    @staticmethod
    def lower(dr):
        return AlteraDDRInputImpl(dr.i, dr.o, Signal(len(dr.o)), dr.clk)

# Special Overrides --------------------------------------------------------------------------------

altera_special_overrides = {
    AsyncResetSynchronizer: AlteraAsyncResetSynchronizer,
    DifferentialInput:      AlteraDifferentialInput,
    DifferentialOutput:     AlteraDifferentialOutput,
    DDROutput:              AlteraDDROutput,
    DDRInput:               AlteraDDRInput,
    SDROutput:              AlteraSDROutput,
    SDRInput:               AlteraSDRInput,
}

# Agilex5 AsyncResetSynchronizer -------------------------------------------------------------------

class Agilex5AsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        self.specials += Instance("altera_std_synchronizer_nocut", name=f"ars_cd_{cd.name}_ff0",
            p_depth     = 3,
            p_rst_value = 0,
            i_clk       = cd.clk,
            i_reset_n   = Constant(1, 1),
            i_din       = async_reset,
            o_dout      = cd.rst,
        )

class Agilex5AsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return Agilex5AsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

# Agilex5 DDROutput --------------------------------------------------------------------------------

class Agilex5DDROutputImpl(Module):
    def __init__(self, i1, i2, o, clk):
        for j in range(len(o)):
            self.specials += Instance("tennm_ph2_ddio_out",
                p_mode      = "MODE_DDR",
                p_asclr_ena = "ASCLR_ENA_NONE",
                p_sclr_ena  = "SCLR_ENA_NONE",
                o_dataout   = o[j],
                i_datainlo  = i2[j],
                i_datainhi  = i1[j],
                i_clk       = clk,
                i_ena       = Constant(1, 1),
                i_areset    = Constant(1, 1),
                i_sreset    = Constant(1, 1),
            )

class Agilex5DDROutput:
    @staticmethod
    def lower(dr):
        return Agilex5DDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)

# Agilex5 DDRInput ---------------------------------------------------------------------------------

class Agilex5DDRInputImpl(Module):
    def __init__(self, i, o1, o2, clk):
        for j in range(len(i)):
            self.specials += Instance("tennm_ph2_ddio_in",
                p_mode      = "MODE_DDR",
                p_asclr_ena = "ASCLR_ENA_NONE",
                p_sclr_ena  = "SCLR_ENA_NONE",
                i_clk       = clk,
                i_datain    = i[j],
                o_regouthi  = o1[j],
                o_regoutlo  = o2[j],
                i_ena       = Constant(1, 1),
                i_areset    = Constant(1, 1),
                i_sreset    = Constant(1, 1),
            )

class Agilex5DDRInput:
    @staticmethod
    def lower(dr):
        return Agilex5DDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)

# Agilex5 SDROutput --------------------------------------------------------------------------------

class Agilex5SDROutput:
    @staticmethod
    def lower(dr):
        return Agilex5DDROutputImpl(dr.i, dr.i, dr.o, dr.clk)

# Agilex5 SDRInput ---------------------------------------------------------------------------------

class Agilex5SDRInput:
    @staticmethod
    def lower(dr):
        return Agilex5DDRInputImpl(dr.i, dr.o, Signal(len(dr.o)), dr.clk)

# Agilex5 SDRTristate ------------------------------------------------------------------------------

class Agilex5SDRTristateImpl(Module):
    def __init__(self, io, o, oe, i, clk):
        _i  = Signal().like(i)
        _o  = Signal().like(o)
        _oe = Signal().like(oe)
        self.specials += [
            SDRIO(o, _o, clk),
            SDRIO(oe, _oe, clk),
            SDRIO(_i, i, clk)
        ]
        
        for j in range(len(io)):
            self.specials += [
                Instance("tennm_ph2_io_ibuf",
                    p_bus_hold = "BUS_HOLD_OFF",
                    io_i       = io[j], # FIXME: its an input but io is needed to have correct dir at top module
                    o_o        = _i[j],
                ),
                Instance("tennm_ph2_io_obuf",
                    p_open_drain = "OPEN_DRAIN_OFF",
                    i_i          = _o[j],
                    i_oe         = _oe[j],
                    io_o         = io[j], # FIXME: its an output but io is needed to have correct dir at top module
                ),
            ]

class Agilex5SDRTristate(Module):
    @staticmethod
    def lower(dr):
        return Agilex5SDRTristateImpl(dr.io, dr.o, dr.oe, dr.i, dr.clk)

# Agilex5 Special Overrides ------------------------------------------------------------------------

agilex5_special_overrides = {
    AsyncResetSynchronizer: Agilex5AsyncResetSynchronizer,
    DifferentialInput:      AlteraDifferentialInput,
    DifferentialOutput:     AlteraDifferentialOutput,
    DDROutput:              Agilex5DDROutput,
    DDRInput:               Agilex5DDRInput,
    SDROutput:              Agilex5SDROutput,
    SDRInput:               Agilex5SDRInput,
    SDRTristate:            Agilex5SDRTristate,
}
