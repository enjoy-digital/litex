# Copyright 2014-2015 Robert Jordens <jordens@gmail.com>
# License: BSD

from migen import *

from litex.soc.interconnect.csr import *

# XADC ---------------------------------------------------------------------------------------------

class XADC(Module, AutoCSR):
    def __init__(self):
        # Temperature(°C) = adc_value*503.975/4096 - 273.15
        self.temperature = CSRStatus(12)

        # Voltage(V) = adc_value*)/4096*3
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
        drdy    = Signal()

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
            i_VAUXN=0, i_VAUXP=1, i_VN=0, i_VP=1,
            i_CONVST=0, i_CONVSTCLK=0, i_RESET=ResetSignal(),
            o_DO=data, o_DRDY=drdy, i_DADDR=channel, i_DCLK=ClockSignal(),
            i_DEN=eoc, i_DI=0, i_DWE=0,
            # o_JTAGBUSY=, o_JTAGLOCKED=, o_JTAGMODIFIED=, o_MUXADDR=,
        )

        channels = {
            0: self.temperature,
            1: self.vccint,
            2: self.vccaux,
            6: self.vccbram
        }

        self.sync += [
                If(drdy,
                    Case(channel, dict(
                        (k, v.status.eq(data >> 4))
                    for k, v in channels.items()))
                )
        ]
