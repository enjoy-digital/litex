#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import MultiReg

from litex.soc.interconnect.csr import *

class MCPWM(Module, AutoCSR):
    """ Multi-Channel Pulse Width Modulation

    """
    def __init__(self, pads=None, clock_domain="sys", with_csr=True,
        num_channels   = 8,
        default_enable = 1,
        default_width  = 512,
        default_period = 1024):

        self.default_width = default_width
        self.n = num_channels
        if pads is None:
            self.pwm = pads = Signal(self.n)
        else:
            self.n = len(pads)
            self.pwm = Signal(self.n)

        self.reset   = Signal()
        self.enable  = Signal(self.n, reset=default_enable*(2**self.n-1))
        self.enabled = Signal()
        self.period  = Signal(32, reset=default_period)
        for i in range(self.n):
            setattr(self, """pw{i}""".format(i=i), Signal(32, reset=default_width))
     
        self.counter = Signal(32, reset_less=True)

        sync = getattr(self.sync, clock_domain)
        sync += [
                If(self.enabled & ~self.reset,
                    self.counter.eq(self.counter + 1),
                    If(self.counter >= (self.period - 1),
                        self.counter.eq(0)
                    ),
#                    If(self.counter < self.pw0,
#                        pads.eq(pads ^ 0x05)
#                    ).Else(
#                        pads.eq(pads ^ 0x02)
#                    )
                ).Else(
#                    pads.eq(2**self.n-1),
                    self.counter.eq(0)
                )
            ]
        for i in range(self.n):
            sync += [
                    If(self.enable[i],
                        If(self.counter < getattr(self, """pw{i}""".format(i=i)),
                            self.pwm[i].eq(1)
                        ).Else(
                            self.pwm[i].eq(0)
                        )
                    ).Else(
                        self.pwm[i].eq(0)
                    )
            ]
        
        self.comb += pads.eq(self.pwm)
        self.comb += self.enabled.eq(self.enable != 0)

        if with_csr:
            self.add_csr(clock_domain)

    def add_csr(self, clock_domain):
        self._enable = CSRStorage(self.n, description="""MCPWM Enable.\n
            Write ``1`` to enable MCPWM.""",
            reset = self.enable.reset)
        
        self._period = CSRStorage(32, reset_less=True, description="""MCPWM Period.\n
            Defines the *Period* of the MCPWM in ``{cd}_clk`` cycles.""".format(cd=clock_domain),
            reset = self.period.reset)
        
        for i in range(self.n):
            setattr(self, """_pw{i}""".format(i=i), CSRStorage(32, name="""pw{i}""".format(i=i),  reset_less=True, description="""PWM Width.\n
            Defines the *Duty cycle* of the MCPWM. PWM is active high for *Width* ``{cd}_clk`` cycles and
            active low for *Period - Width* ``{cd}_clk`` cycles.""".format(cd=clock_domain),
            reset = getattr(self, """pw{i}""".format(i=i)).reset))

        #self._counter = CSRStatus(32, description="""MCPWM Counter.\n""")

        n = 0 if clock_domain == "sys" else 2
        
        for i in range(self.n):
            self.specials += MultiReg(getattr(self, """_pw{i}""".format(i=i)).storage,  getattr(self, """pw{i}""".format(i=i)),  n=n)
        
        self.specials += [
            MultiReg(self._enable.storage, self.enable, n=n),
            MultiReg(self._period.storage, self.period, n=n),
            #MultiReg(self._counter.status, self.counter, n=n),
        ]
                    
# Pulse Width Modulation ---------------------------------------------------------------------------

class PWM(Module, AutoCSR):
    """Pulse Width Modulation

    Provides the minimal hardware to do Pulse Width Modulation.

    Pulse Width Modulation can be useful for various purposes: dim leds, regulate a fan, control
    an oscillator. Software can configure the PWM width and period and enable/disable it.
    """
    def __init__(self, pwm=None, clock_domain="sys", with_csr=True,
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

        counter = Signal(32, reset_less=True)

        sync = getattr(self.sync, clock_domain)
        sync += [
            If(self.enable & ~self.reset,
                counter.eq(counter + 1),
                If(counter < self.width,
                    pwm.eq(1)
                ).Else(
                    pwm.eq(0)
                ),
                If(counter >= (self.period - 1),
                    counter.eq(0)
                )
            ).Else(
                counter.eq(0),
                pwm.eq(0)
            )
        ]

        if with_csr:
            self.add_csr(clock_domain)

    def add_csr(self, clock_domain):
        self._enable = CSRStorage(description="""PWM Enable.\n
            Write ``1`` to enable PWM.""",
            reset = self.enable.reset)
        self._width  = CSRStorage(32, reset_less=True, description="""PWM Width.\n
            Defines the *Duty cycle* of the PWM. PWM is active high for *Width* ``{cd}_clk`` cycles and
            active low for *Period - Width* ``{cd}_clk`` cycles.""".format(cd=clock_domain),
            reset = self.width.reset)
        self._period = CSRStorage(32, reset_less=True, description="""PWM Period.\n
            Defines the *Period* of the PWM in ``{cd}_clk`` cycles.""".format(cd=clock_domain),
            reset = self.period.reset)

        n = 0 if clock_domain == "sys" else 2
        self.specials += [
            MultiReg(self._enable.storage, self.enable, n=n),
            MultiReg(self._width.storage,  self.width,  n=n),
            MultiReg(self._period.storage, self.period, n=n),
        ]
