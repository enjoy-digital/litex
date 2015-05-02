from migen.fhdl.std import *
from migen.bank.description import *

from misoclib.cpu import git


class Identifier(Module, AutoCSR):
    def __init__(self, sysid, frequency, revision=None):
        self._sysid = CSRStatus(16)
        self._revision = CSRStatus(32)
        self._frequency = CSRStatus(32)

        ###

        if revision is None:
            revision = git.get_id()

        self.comb += [
            self._sysid.status.eq(sysid),
            self._revision.status.eq(revision),
            self._frequency.status.eq(frequency)
        ]
