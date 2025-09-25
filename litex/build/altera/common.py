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
                i_datain_h = i1[j], # rising edge
                i_datain_l = i2[j], # falling edge
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
                o_dataout_h = o1[j], # rising edge
                o_dataout_l = o2[j], # falling edge
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
        self.specials += Instance("ipm_cdc_async_rst", name=f"ars_cd_{cd.name}_ff0",
            p_NUM_STAGES = 3,
            p_RST_TYPE   = "ACTIVE_HIGH",
            i_clk        = cd.clk,
            i_arst_in    = async_reset,
            o_srst_out   = cd.rst,
        )

class Agilex5AsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return Agilex5AsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

# Agilex5 IBufBase ---------------------------------------------------------------------------------

class Agilex5IBufBase(Module):
    """Base class for tennm_ph2_io_ibuf instantiation."""

    @staticmethod
    def _get_ibuf_params():
        """Return common parameters for tennm_ph2_io_ibuf."""
        return {
            "p_buffer_usage": "REGULAR",
            "p_bus_hold": "BUS_HOLD_OFF",
            "p_equalization": "EQUALIZATION_OFF",
            "p_io_standard": "IO_STANDARD_IOSTD_OFF",
            "p_rzq_id": "RZQ_ID_RZQ0",
            "p_schmitt_trigger": "SCHMITT_TRIGGER_OFF",
            "p_termination": "TERMINATION_RT_OFF",
            "p_toggle_speed": "TOGGLE_SPEED_SLOW",
            "p_usage_mode": "USAGE_MODE_GPIO",
            "p_vref": "VREF_OFF",
            "p_weak_pull_down": "WEAK_PULL_DOWN_OFF",
            "p_weak_pull_up": "WEAK_PULL_UP_OFF",
        }

    def create_ibuf_instance(self, io_signal, o_signal):
        """Create a tennm_ph2_io_ibuf instance with common parameters."""
        return Instance("tennm_ph2_io_ibuf",
            **self._get_ibuf_params(),
            io_i=io_signal,  # FIXME: its an input but io is needed to have correct dir at top module
            o_o=o_signal     # Output from buffer
        )

# Agilex5 OBufBase ---------------------------------------------------------------------------------
class Agilex5OBufBase(Module):
    """Base class for tennm_ph2_io_obuf instantiation."""

    @staticmethod
    def _get_obuf_params():
        """Return common parameters for tennm_ph2_io_obuf."""
        return {
            "p_buffer_usage": "REGULAR",
            "p_dynamic_pull_up_enabled": "FALSE",
            "p_equalization": "EQUALIZATION_OFF",
            "p_io_standard": "IO_STANDARD_IOSTD_OFF",
            "p_open_drain": "OPEN_DRAIN_OFF",
            "p_rzq_id": "RZQ_ID_RZQ0",
            "p_slew_rate": "SLEW_RATE_SLOW",
            "p_termination": "TERMINATION_SERIES_OFF",
            "p_toggle_speed": "TOGGLE_SPEED_SLOW",
            "p_usage_mode": "USAGE_MODE_GPIO",
        }

    def create_obuf_instance(self, io_signal, i_signal, oe_signal):
        """Create a tennm_ph2_io_obuf instance with common parameters."""
        return Instance("tennm_ph2_io_obuf",
            **self._get_obuf_params(),
            io_o=io_signal,   # FIXME: its an output but io is needed to have correct dir at top module
            i_i=i_signal,     # Input to buffer
            i_oe=oe_signal    # Output enable
        )

# Agilex DifferentialInput ------------------------------------------------------------------------

class Agilex5DifferentialInputImpl(Agilex5IBufBase):
    def __init__(self, i_p, i_n, o):
        self.specials += [
	    Instance("tennm_ph2_io_ibuf",
                **self._get_ibuf_params(),
		i_i    = i_p,
		i_ibar = i_n,
		o_o    = o,
            )
        ]

class Agilex5DifferentialInput:
    @staticmethod
    def lower(dr):
        return Agilex5DifferentialInputImpl(dr.i_p, dr.i_n, dr.o)

# Agilex DifferentialOutput -----------------------------------------------------------------------

class Agilex5DifferentialOutputImpl(Agilex5OBufBase):
    def __init__(self, i, o_p, o_n):
        _i_b = Signal().like(i)
        _p_n = Signal().like(i)
        self.specials += [
            Instance("tennm_ph2_pseudo_diff_out",
                i_i    = i,
                o_obar = _i_b,
            ),
            Instance("tennm_ph2_io_obuf",
                **self._get_obuf_params(),
                i_i          = i,
                o_o          = o_p,
                o_posbuf_out = _p_n, # to neg buf
            ),
            Instance("tennm_ph2_io_obuf",
                **self._get_obuf_params(),
                i_i          = _i_b,
                o_o          = o_n,
                i_negbuf_in  = _p_n, # from pos buf
            ),
        ]

class Agilex5DifferentialOutput:
    @staticmethod
    def lower(dr):
        return Agilex5DifferentialOutputImpl(dr.i, dr.o_p, dr.o_n)

# Agilex5 DDROutput --------------------------------------------------------------------------------

class Agilex5DDROutputImpl(Module):
    def __init__(self, i1, i2, o, clk):
        for j in range(len(o)):
            self.specials += Instance("tennm_ph2_ddio_out",
                p_mode      = "MODE_DDR",
                p_asclr_ena = "ASCLR_ENA_NONE",
                p_sclr_ena  = "SCLR_ENA_NONE",
                o_dataout   = o[j],
                i_datainlo  = i1[j], # rising edge
                i_datainhi  = i2[j], # falling edge
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
                o_regoutlo  = o1[j], # rising edge
                o_regouthi  = o2[j], # falling edge
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

class Agilex5SDRTristateImpl(Agilex5IBufBase, Agilex5OBufBase):
    def __init__(self, io, o, oe, i, clk):
        super().__init__()
        _i  = Signal().like(i) if i is not None else None
        _o  = Signal().like(o)
        _oe = Signal().like(oe)
        self.specials += [
            SDRIO(o, _o, clk),
            SDRIO(oe, _oe, clk)
        ]
        if _i is not None:
            self.specials += SDRIO(_i, i, clk)

        for j in range(len(io)):
            if _i is not None:
                self.specials += self.create_ibuf_instance(
                    io_signal = io[j],  # Input to buffer
                    o_signal  = _i[j],  # Output from buffer
                )

            self.specials += self.create_obuf_instance(
                io_signal=io[j],  # Output from buffer
                i_signal=_o[j],   # Input to buffer
                oe_signal=_oe[j]  # Output enable
            )

class Agilex5SDRTristate(Module):
    @staticmethod
    def lower(dr):
        return Agilex5SDRTristateImpl(dr.io, dr.o, dr.oe, dr.i, dr.clk)

# Agilex5 Tristate ---------------------------------------------------------------------------------

class Agilex5TristateImpl(Agilex5IBufBase, Agilex5OBufBase):
    def __init__(self, io, o, oe, i):
        super().__init__()
        nbits, _ = value_bits_sign(io)
        for bit in range(nbits):
            # Handle single-bit vs multi-bit signals
            io_signal = io[bit] if nbits > 1 else io
            o_signal = o[bit] if nbits > 1 else o
            oe_signal = oe[bit] if len(oe) == nbits > 1 else oe
            i_signal = i[bit] if nbits > 1 and i is not None else i

            if i is not None:
                self.specials += self.create_ibuf_instance(
                    io_signal = io_signal,  # Input to buffer
                    o_signal  = i_signal    # Output from buffer
                )
            self.specials += self.create_obuf_instance(
                io_signal = io_signal,  # Output from buffer
                i_signal  = o_signal,   # Input to buffer
                oe_signal = oe_signal   # Output enable
            )

class Agilex5Tristate:
    @staticmethod
    def lower(dr):
        return Agilex5TristateImpl(dr.target, dr.o, dr.oe, dr.i)

# Agilex5 Special Overrides ------------------------------------------------------------------------

agilex5_special_overrides = {
    AsyncResetSynchronizer: Agilex5AsyncResetSynchronizer,
    DifferentialInput:      Agilex5DifferentialInput,
    DifferentialOutput:     Agilex5DifferentialOutput,
    DDROutput:              Agilex5DDROutput,
    DDRInput:               Agilex5DDRInput,
    SDROutput:              Agilex5SDROutput,
    SDRInput:               Agilex5SDRInput,
    SDRTristate:            Agilex5SDRTristate,
    Tristate:               Agilex5Tristate,
}
