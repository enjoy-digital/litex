from migen.fhdl.std import *
from migen.bank.description import *

from misoclib.identifier import git

class Identifier(Module, AutoCSR):
	def __init__(self, sysid, frequency, revision=None):
		self._r_sysid = CSRStatus(16)
		self._r_revision = CSRStatus(32)
		self._r_frequency = CSRStatus(32)
		
		###

		if revision is None:
			revision = git.get_id()

		self.comb += [
			self._r_sysid.status.eq(sysid),
			self._r_revision.status.eq(revision),
			self._r_frequency.status.eq(frequency)
		]
