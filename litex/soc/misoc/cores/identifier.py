from migen import *

from misoc.interconnect.csr import *


class Identifier(Module, AutoCSR):
    def __init__(self, sysid, frequency, revision=None):
        self._sysid = CSRStatus(16)
        self._frequency = CSRStatus(32)

        ###

        self.comb += [
            self._sysid.status.eq(sysid),
            self._frequency.status.eq(frequency)
        ]
