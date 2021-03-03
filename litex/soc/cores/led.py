#
# This file is part of LiteX.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.misc import WaitTimer

from litex.soc.interconnect.csr import *

# Led Chaser ---------------------------------------------------------------------------------------

_CHASER_MODE  = 0
_CONTROL_MODE = 1

class LedChaser(Module, AutoCSR):
    def __init__(self, pads, sys_clk_freq, period=1e0):
        self.pads = pads
        self._out = CSRStorage(len(pads), description="Led Output(s) Control.")

        # # #

        n      = len(pads)
        chaser = Signal(n)
        mode   = Signal(reset=_CHASER_MODE)
        timer  = WaitTimer(int(period*sys_clk_freq/(2*n)))
        self.submodules += timer
        self.comb += timer.wait.eq(~timer.done)
        self.sync += If(timer.done, chaser.eq(Cat(~chaser[-1], chaser)))
        self.sync += If(self._out.re, mode.eq(_CONTROL_MODE))
        self.comb += [
            If(mode == _CONTROL_MODE,
                pads.eq(self._out.storage)
            ).Else(
                pads.eq(chaser)
            )
        ]

    def add_pwm(self, default_width=512, default_period=1024, with_csr=True):
        from litex.soc.cores.pwm import PWM
        self.submodules.pwm = PWM(
            with_csr       = with_csr,
            default_enable = 1,
            default_width  = default_width,
            default_period = default_period
        )
        # Use PWM as Output Enable for pads.
        self.comb += If(~self.pwm.pwm, self.pads.eq(0))
