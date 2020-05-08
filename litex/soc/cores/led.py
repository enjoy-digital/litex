# This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *
from migen.genlib.misc import WaitTimer

from litex.soc.interconnect.csr import *

# Led Chaser ---------------------------------------------------------------------------------------

class LedChaser(Module, AutoCSR):
    def __init__(self, pads, sys_clk_freq, period=1e0):
        self.control  = CSRStorage(fields=[
            CSRField("mode", size=2, values=[
                ("``0b0``", "Chaser mode."),
                ("``0b1``", "CPU mode."),
            ])
        ])
        self.value = CSRStorage(len(pads), description="Control value when in CPU mode.")

        # # #

        n      = len(pads)
        chaser = Signal(n)
        timer  = WaitTimer(int(period*sys_clk_freq/(2*n)))
        self.submodules += timer
        self.comb += timer.wait.eq(~timer.done)
        self.sync += If(timer.done, chaser.eq(Cat(~chaser[-1], chaser)))
        self.comb += [
            If(self.control.fields.mode,
                pads.eq(self.value.storage)
            ).Else(
                pads.eq(chaser)
            )
        ]
