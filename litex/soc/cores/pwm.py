# This file is Copyright (c) 2015 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *
from migen.genlib.cdc import MultiReg

from litex.soc.interconnect.csr import *

# Pulse Width Modulation ---------------------------------------------------------------------------

class PWM(Module, AutoCSR):
    """Pulse Width Modulation

    Provides the minimal hardware to do Pulse Width Modulation.

    Pulse Width Modulation can be useful for various purposes: dim leds, regulate a fan, control
    an oscillator. Software can configure the PWM width and period and enable/disable it.
    """
    def __init__(self, pwm=None, clock_domain="sys"):
        if pwm is None:
            self.pwm = pwm = Signal()
        self._enable = CSRStorage(reset=1)
        self._width  = CSRStorage(32, reset=2**19)
        self._period = CSRStorage(32, reset=2**20)

        # # #

        counter = Signal(32)
        enable  = Signal()
        width   = Signal(32)
        period  = Signal(32)

        # Resynchronize to clock_domain ------------------------------------------------------------
        self.specials += [
            MultiReg(self._enable.storage, enable, clock_domain),
            MultiReg(self._width.storage,  width,  clock_domain),
            MultiReg(self._period.storage, period, clock_domain),
        ]

        # PWM generation  --------------------------------------------------------------------------
        sync = getattr(self.sync, clock_domain)
        sync += \
            If(enable,
                If(counter < width,
                    pwm.eq(1)
                ).Else(
                    pwm.eq(0)
                ),
                If(counter == period-1,
                    counter.eq(0)
                ).Else(
                    counter.eq(counter+1)
                )
            ).Else(
                counter.eq(0),
                pwm.eq(0)
            )
