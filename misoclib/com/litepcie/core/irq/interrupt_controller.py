from migen.fhdl.std import *
from migen.bank.description import *

from misoclib.com.litepcie.common import *


class InterruptController(Module, AutoCSR):
    def __init__(self, n_irqs=32):
        self.irqs = Signal(n_irqs)
        self.source = Source(interrupt_layout())

        self._enable = CSRStorage(n_irqs)
        self._clear = CSR(n_irqs)
        self._vector = CSRStatus(n_irqs)

        # # #

        enable = self._enable.storage
        clear = Signal(n_irqs)
        self.comb += If(self._clear.re, clear.eq(self._clear.r))

        # memorize and clear irqs
        vector = self._vector.status
        self.sync += vector.eq(~clear & (vector | self.irqs))

        self.comb += self.source.stb.eq((vector & enable) != 0)
