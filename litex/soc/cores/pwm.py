#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import MultiReg

from litex.gen import *

from litex.soc.interconnect.csr import *

# Pulse Width Modulation ---------------------------------------------------------------------------

def _validate_counter_width(counter_width, default_width, default_period):
    if not isinstance(counter_width, int) or isinstance(counter_width, bool) or not 1 <= counter_width <= 32:
        raise ValueError("PWM counter_width must be an integer from 1 to 32.")
    if not 0 <= default_width < 2**counter_width or not 0 <= default_period < 2**counter_width:
        raise ValueError("PWM default width and period must fit counter_width.")


class PWM(LiteXModule):
    """Pulse Width Modulation

    Provides the minimal hardware to do Pulse Width Modulation.

    Pulse Width Modulation can be useful for various purposes: dim leds, regulate a fan, control
    an oscillator. Software can configure the PWM width and period and enable/disable it.

    ``counter_width`` optionally reduces the counter, comparators and width/period CSRs for
    applications that do not need 32-bit resolution. The default register layout is unchanged.
    Width/period updates are not atomic; disable the output and allow controls to settle when
    reconfiguring a PWM in a different clock domain.
    """
    def __init__(self, pwm=None, clock_domain="sys", counter=None, with_csr=True,
        default_enable = 0,
        default_width  = 0,
        default_period = 0,
        counter_enable = None,
        counter_width  = 32):
        _validate_counter_width(counter_width, default_width, default_period)
        if pwm is None:
            self.pwm = pwm = Signal()
        self.reset  = Signal()
        self.enable = Signal(reset=default_enable)
        self.width  = Signal(counter_width, reset=default_width)
        self.period = Signal(counter_width, reset=default_period)

        # # #

        sync = getattr(self.sync, clock_domain)

        # PWM Counter/Period logic.
        if counter is None:
            # A shared timebase can run while this channel's output is disabled.
            if counter_enable is None:
                counter_enable = self.enable
            self.counter = counter = Signal(counter_width, reset_less=True)
            sync += [
                counter.eq(0),
                If(counter_enable & ~self.reset,
                    If(counter < (self.period - 1),
                        counter.eq(counter + 1)
                    )
                )
            ]

        # PWM Width logic.
        sync += pwm.eq(self.enable & (counter < self.width))

        if with_csr:
            self.add_csr(clock_domain)

    def add_enable_width_csr(self, clock_domain):
        self._enable = CSRStorage(description="""PWM Enable.\n
            Write ``1`` to enable PWM.""",
            reset = self.enable.reset)
        self._width  = CSRStorage(len(self.width), reset_less=True, description="""PWM Width.\n
            Defines the *Duty cycle* of the PWM. PWM is active high for *Width* ``{cd}_clk`` cycles and
            active low for *Period - Width* ``{cd}_clk`` cycles.""".format(cd=clock_domain),
            reset = self.width.reset)

        n = 0 if clock_domain == "sys" else 2
        self.specials += [
            MultiReg(self._enable.storage, self.enable, odomain=clock_domain, n=n),
            MultiReg(self._width.storage,  self.width,  odomain=clock_domain, n=n),
        ]

    def add_period_csr(self, clock_domain):
        self._period = CSRStorage(len(self.period), reset_less=True, description="""PWM Period.\n
            Defines the *Period* of the PWM in ``{cd}_clk`` cycles.""".format(cd=clock_domain),
            reset = self.period.reset)

        n = 0 if clock_domain == "sys" else 2
        self.specials += MultiReg(self._period.storage, self.period, odomain=clock_domain, n=n)

    def add_csr(self, clock_domain):
        self.add_enable_width_csr(clock_domain)
        self.add_period_csr(clock_domain)

# Multi Channel Pulse Width Modulation -------------------------------------------------------------

class MultiChannelPWM(LiteXModule):
    """Multi-Channel Pulse Width Modulation

    PWM module with Multi-Channel support.

    Channel 0 supplies the shared period. The timebase runs while any channel is enabled;
    disabling an individual channel only disables its output.
    """
    def __init__(self, pads, clock_domain="sys",
        default_enable = 0,
        default_width  = 0,
        default_period = 0,
        counter_width  = 32):
        _validate_counter_width(counter_width, default_width, default_period)

        # # #

        nchannels = len(pads)

        counter = Signal(counter_width, reset_less=True)
        counter_enable = Signal()
        enables = []
        for n in range(nchannels):
            pwm = PWM(
                pwm            = pads[n],
                clock_domain   = clock_domain,
                with_csr       = False,
                counter        = None if n == 0 else counter,
                default_enable = default_enable,
                default_width  = default_width,
                default_period = default_period,
                counter_enable = counter_enable,
                counter_width  = counter_width,
            )

            if n == 0:
                self.comb += counter.eq(pwm.counter)
                pwm.add_period_csr(clock_domain)
            pwm.add_enable_width_csr(clock_domain)
            self.add_module(name=f"channel{n}", module=pwm)
            enables.append(pwm.enable)
        self.comb += counter_enable.eq(Reduce("OR", enables))
