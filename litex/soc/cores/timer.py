# This file is Copyright (c) 2013-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2019 Sean Cross <sean@xobs.io>
# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD


from migen import *

from litex.soc.interconnect.csr import *
from litex.soc.interconnect.csr_eventmanager import *


class Timer(Module, AutoCSR):
    def __init__(self, width=32):
        self._load = CSRStorage(width, description=
            """Load value when timer is (re-)enabled.
            This register is only used to create a One-Shot timer and specify the timer's duration
            in clock cycles: Disable the timer, write load value and re-enable the timer""")
        self._reload = CSRStorage(width, description=
            """Reload value when timer reaches 0.
            This register is used to create a Periodic timer and specify the timer's period in clock
            cycles. For a One-Shot timer, this register need to be set to 0.""")
        self._en = CSRStorage(1, description=
            """Enable. Write 1 to enable/start the timer, 0 to disable the timer""")
        self._update_value = CSRStorage(1, description=
            """Update. Write 1 to latch current countdown to value register.""")
        self._value = CSRStatus(width, description="""Latched countdown value""")

        self.submodules.ev = EventManager()
        self.ev.zero = EventSourceProcess()
        self.ev.finalize()

        # # #

        value = Signal(width)
        self.sync += [
            If(self._en.storage,
                If(value == 0,
                    # set reload to 0 to disable reloading
                    value.eq(self._reload.storage)
                ).Else(
                    value.eq(value - 1)
                )
            ).Else(
                value.eq(self._load.storage)
            ),
            If(self._update_value.re, self._value.status.eq(value))
        ]
        self.comb += self.ev.zero.trigger.eq(value != 0)
