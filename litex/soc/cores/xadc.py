#
# This file is part of LiteX.
#
# Copyright (c) 2014-2015 Robert Jordens <jordens@gmail.com>
# Copyright (c) 2019 bunnie <bunnie@kosagi.com>
# Copyright (c) 2019-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.soc.interconnect.csr import *

# XADC ---------------------------------------------------------------------------------------------

analog_layout = [("vauxp", 16), ("vauxn", 16), ("vp", 1), ("vn", 1)]

class XADC(Module, AutoCSR):
    def __init__(self, analog_pads=None):
        # Temperature
        self.temperature = CSRStatus(12, description="""Raw Temperature value from XADC.\n
            Temperature (°C) = ``Value`` x 503.975 / 4096 - 273.15.""")

        # Voltages
        self.vccint  = CSRStatus(12, description="""Raw VCCINT value from XADC.\n
            VCCINT (V) = ``Value`` x 3 / 4096.""")
        self.vccaux  = CSRStatus(12, description="""Raw VCCAUX value from XADC.\n
            VCCAUX (V) = ``Value`` x 3 / 4096.""")
        self.vccbram = CSRStatus(12, description="""Raw VCCBRAM value from XADC.\n
            VCCBRAM (V) = ``Value`` x 3 / 4096.""")

        # End of Convertion/Sequence
        self.eoc = CSRStatus(description="End of Convertion Status, ``1``: Convertion Done.")
        self.eos = CSRStatus(description="End of Sequence Status, ``1``: Sequence Done.")

        # Alarms
        self.alarm = Signal(8)
        self.ot    = Signal()

        # # #

        busy    = Signal()
        channel = Signal(7)
        eoc     = Signal()
        eos     = Signal()

        # XADC instance ----------------------------------------------------------------------------
        self.dwe  = Signal()
        self.den  = Signal()
        self.drdy = Signal()
        self.dadr = Signal(7)
        self.di   = Signal(16)
        self.do   = Signal(16)
        self.drp_en = Signal()
        self.specials += Instance("XADC",
            # From ug480
            p_INIT_40=0x9000, p_INIT_41=0x2ef0, p_INIT_42=0x0400,
            p_INIT_48=0x4701, p_INIT_49=0x000f,
            p_INIT_4A=0x4700, p_INIT_4B=0x0000,
            p_INIT_4C=0x0000, p_INIT_4D=0x0000,
            p_INIT_4E=0x0000, p_INIT_4F=0x0000,
            p_INIT_50=0xb5ed, p_INIT_51=0x5999,
            p_INIT_52=0xa147, p_INIT_53=0xdddd,
            p_INIT_54=0xa93a, p_INIT_55=0x5111,
            p_INIT_56=0x91eb, p_INIT_57=0xae4e,
            p_INIT_58=0x5999, p_INIT_5C=0x5111,
            o_ALM       = self.alarm,
            o_OT        = self.ot,
            o_BUSY      = busy,
            o_CHANNEL   = channel,
            o_EOC       = eoc,
            o_EOS       = eos,
            i_VAUXP     = 0 if analog_pads is None else analog_pads.vauxp,
            i_VAUXN     = 0 if analog_pads is None else analog_pads.vauxn,
            i_VP        = 0 if analog_pads is None else analog_pads.vp,
            i_VN        = 0 if analog_pads is None else analog_pads.vn,
            i_CONVST    = 0,
            i_CONVSTCLK = 0,
            i_RESET     = ResetSignal(),
            i_DCLK      = ClockSignal(),
            i_DWE       = self.dwe,
            i_DEN       = self.den,
            o_DRDY      = self.drdy,
            i_DADDR     = self.dadr,
            i_DI        = self.di,
            o_DO        = self.do
        )
        self.comb += [
            If(~self.drp_en,
                self.den.eq(eoc),
                self.dadr.eq(channel),
            )
        ]

        # Channels update --------------------------------------------------------------------------
        channels = {
            0: self.temperature,
            1: self.vccint,
            2: self.vccaux,
            6: self.vccbram
        }
        self.sync += [
                If(self.drdy,
                    Case(channel, dict(
                        (k, v.status.eq(self.do >> 4))
                    for k, v in channels.items()))
                )
        ]

        # End of Convertion/Sequence update --------------------------------------------------------
        self.sync += [
            self.eoc.status.eq((self.eoc.status & ~self.eoc.we) | eoc),
            self.eos.status.eq((self.eos.status & ~self.eos.we) | eos),
        ]

    def expose_drp(self):
        self.drp_enable = CSRStorage() # Set to 1 to use DRP and disable auto-sampling
        self.drp_read   = CSR()
        self.drp_write  = CSR()
        self.drp_drdy   = CSRStatus()
        self.drp_adr    = CSRStorage(7,  reset_less=True)
        self.drp_dat_w  = CSRStorage(16, reset_less=True)
        self.drp_dat_r  = CSRStatus(16)

        # # #

        den_pipe = Signal() # add a register to ease timing closure of den

        self.comb += [
            self.di.eq(self.drp_dat_w.storage),
            self.drp_dat_r.status.eq(self.do),
            If(self.drp_en,
               self.den.eq(den_pipe),
               self.dadr.eq(self.drp_adr.storage),
            )
        ]
        self.sync += [
            self.dwe.eq(self.drp_write.re),
            self.drp_en.eq(self.drp_enable.storage),
            den_pipe.eq(self.drp_read.re | self.drp_write.re),
            If(self.drp_read.re | self.drp_write.re,
                self.drp_drdy.status.eq(0)
            ).Elif(self.drdy,
                self.drp_drdy.status.eq(1)
            )
        ]
