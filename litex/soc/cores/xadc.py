# Copyright 2014-2015 Robert Jordens <jordens@gmail.com>
# License: BSD

from migen import *

from litex.soc.interconnect.csr import *

# XADC ---------------------------------------------------------------------------------------------

analog_layout = [("vauxp", 16), ("vauxn", 16), ("vp", 1), ("vn", 1)]

class XADC(Module, AutoCSR):
    def __init__(self, analog=None):
        # add a CSR bank for controlling the XADC DRP. Adds bloat to the gateware
        # if you're not using this feature, but makes the code more elegant.
        self.drp_enable = CSRStorage()  # must set this to 1 to use DRP, otherwise auto-sample
        self.drp_read = CSR()
        self.drp_write = CSR()
        self.drp_drdy = CSRStatus()
        self.drp_adr = CSRStorage(7)
        self.drp_dat_w = CSRStorage(16)
        self.drp_dat_r = CSRStatus(16)

        # monitor EOC/EOS so we can poll if the ADC has been updated
        self.eoc = CSRStatus()
        self.eos = CSRStatus()
        # TODO: hook up the alarm as interrupt

        drp_drdy = Signal()

        if analog == None:
            analog = Record(analog_layout)
            self.comb += [
                analog.vauxp.eq(0),
                analog.vauxn.eq(0),
                analog.vp.eq(0),
                analog.vn.eq(0),
            ]

        self.sync += [
            If(self.drp_read.re | self.drp_write.re,
               self.drp_drdy.status.eq(0)
            ).Elif(drp_drdy,
               self.drp_drdy.status.eq(1)
            )
        ]

        # Temperature(°C) = adc_value*503.975/4096 - 273.15
        self.temperature = CSRStatus(12)

        # Voltage(V) =  as uadc_value*)/4096*3
        self.vccint  = CSRStatus(12)
        self.vccaux  = CSRStatus(12)
        self.vccbram = CSRStatus(12)

        # Alarms
        self.alarm = Signal(8)
        self.ot    = Signal()

        # # #

        busy    = Signal()
        channel = Signal(7)
        eoc     = Signal()
        eos     = Signal()
        data    = Signal(16)

        auto = Signal()
        self.comb += auto.eq(~self.drp_enable.storage)
        adr = Signal(7)
        self.comb += [
            If(auto,
               adr.eq(channel),
            ).Else(
               adr.eq(self.drp_adr.storage)
            )
        ]
        self.specials += Instance("XADC",
            # from ug480
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
            o_ALM=self.alarm, o_OT=self.ot,
            o_BUSY=busy, o_CHANNEL=channel, o_EOC=eoc, o_EOS=eos,
            i_VAUXN=analog.vauxn, i_VAUXP=analog.vauxp, i_VN=analog.vn, i_VP=analog.vp,
            i_CONVST=0, i_CONVSTCLK=0, i_RESET=ResetSignal(),
            o_DO=data, o_DRDY=drp_drdy, i_DADDR=adr, i_DCLK=ClockSignal(),
            i_DEN=(auto & eoc) | (~auto & (self.drp_read.re | self.drp_write.re)),
            i_DI=self.drp_dat_w.storage, i_DWE=self.drp_write.re,
            # o_JTAGBUSY=, o_JTAGLOCKED=, o_JTAGMODIFIED=, o_MUXADDR=,
        )
        self.sync += [
            If(drp_drdy,
               self.drp_dat_r.status.eq(data),
            ).Else(
               self.drp_dat_r.status.eq(self.drp_dat_r.status),
            )
        ]

        self.sync += [
            self.eoc.status.eq((~self.eoc.we & self.eoc.status) | eoc),
            self.eos.status.eq((~self.eos.we & self.eos.status) | eos),
        ]

        channels = {
            0: self.temperature,
            1: self.vccint,
            2: self.vccaux,
            6: self.vccbram
        }

        self.sync += [
                If(drp_drdy & auto,
                    Case(channel, dict(
                        (k, v.status.eq(data >> 4))
                    for k, v in channels.items()))
                )
        ]
