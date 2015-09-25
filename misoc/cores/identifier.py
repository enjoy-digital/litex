import subprocess

from migen import *

from misoc.interconnect.csr import *


def get_id():
    output = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("ascii")
    return int(output[:8], 16)


class Identifier(Module, AutoCSR):
    def __init__(self, sysid, frequency, revision=None):
        self._sysid = CSRStatus(16)
        self._revision = CSRStatus(32)
        self._frequency = CSRStatus(32)

        ###

        if revision is None:
            revision = get_id()

        self.comb += [
            self._sysid.status.eq(sysid),
            self._revision.status.eq(revision),
            self._frequency.status.eq(frequency)
        ]
