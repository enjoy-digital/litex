#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

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
    def __init__(self, pwm=None, clock_domain="sys", counter=None, with_csr=True,
        default_enable = 0,
        default_width  = 0,
        default_period = 0):
        if pwm is None:
            self.pwm = pwm = Signal()
        self.reset  = Signal()
        self.enable = Signal(reset=default_enable)
        self.width  = Signal(32, reset=default_width)
        self.period = Signal(32, reset=default_period)

        # # #

        sync = getattr(self.sync, clock_domain)

        # PWM Counter/Period logic.
        if counter is None:
            self.counter = counter = Signal(32, reset_less=True)
            sync += [
                counter.eq(0),
                If(self.enable & ~self.reset,
                    If(counter < (self.period - 1),
                        counter.eq(counter + 1)
                    )
                )
            ]

        # PWM Width logic.
        sync += [
            pwm.eq(0),
            If(self.enable & ~self.reset,
                If(counter < self.width,
                    pwm.eq(1)
                )
            )
        ]

        if with_csr:
            self.add_csr(clock_domain)

    def add_enable_width_csr(self, clock_domain):
        self._enable = CSRStorage(description="""PWM Enable.\n
            Write ``1`` to enable PWM.""",
            reset = self.enable.reset)
        self._width  = CSRStorage(32, reset_less=True, description="""PWM Width.\n
            Defines the *Duty cycle* of the PWM. PWM is active high for *Width* ``{cd}_clk`` cycles and
            active low for *Period - Width* ``{cd}_clk`` cycles.""".format(cd=clock_domain),
            reset = self.width.reset)

        n = 0 if clock_domain == "sys" else 2
        self.specials += [
            MultiReg(self._enable.storage, self.enable, n=n),
            MultiReg(self._width.storage,  self.width,  n=n),
        ]

    def add_period_csr(self, clock_domain):
        self._period = CSRStorage(32, reset_less=True, description="""PWM Period.\n
            Defines the *Period* of the PWM in ``{cd}_clk`` cycles.""".format(cd=clock_domain),
            reset = self.period.reset)

        n = 0 if clock_domain == "sys" else 2
        self.specials += MultiReg(self._period.storage, self.period, n=n)

    def add_csr(self, clock_domain):
        self.add_enable_width_csr(clock_domain)
        self.add_period_csr(clock_domain)

# Multi Channel Pulse Width Modulation -------------------------------------------------------------

class MultiChannelPWM(Module, AutoCSR):
    """Multi-Channel Pulse Width Modulation

    PWM module with Multi-Channel support.
    """
    def __init__(self, pads, clock_domain="sys",
        default_enable = 0,
        default_width  = 0,
        default_period = 0):

        # # #

        nchannels = len(pads)

        counter = Signal(32, reset_less=True)
        for n in range(nchannels):
            pwm = PWM(
                pwm            = pads[n],
                clock_domain   = clock_domain,
                with_csr       = False,
                counter        = None if n == 0 else counter,
                default_enable = default_enable,
                default_width  = default_width,
                default_period = default_period,
            )

            if n == 0:
                self.comb += counter.eq(pwm.counter)
                pwm.add_period_csr(clock_domain)
            pwm.add_enable_width_csr(clock_domain)
            self.add_module(name=f"channel{n}", module=pwm)
