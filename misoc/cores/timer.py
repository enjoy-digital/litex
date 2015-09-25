from migen import *

from misoc.interconnect.csr import *
from misoc.interconnect.csr_eventmanager import *


class Timer(Module, AutoCSR):
    def __init__(self, width=32):
        self._load = CSRStorage(width)
        self._reload = CSRStorage(width)
        self._en = CSRStorage()
        self._update_value = CSR()
        self._value = CSRStatus(width)

        self.submodules.ev = EventManager()
        self.ev.zero = EventSourceProcess()
        self.ev.finalize()

        ###

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
