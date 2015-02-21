import subprocess

from migen.fhdl.std import *
from migen.bank.description import *

def get_id():
	output = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("ascii")
	return int(output[:8], 16)

class Identifier(Module, AutoCSR):
	def __init__(self, sysid, frequency, revision=None):
		self._r_sysid = CSRStatus(16)
		self._r_revision = CSRStatus(32)
		self._r_frequency = CSRStatus(32)

		###

		if revision is None:
			revision = get_id()

		self.comb += [
			self._r_sysid.status.eq(sysid),
			self._r_revision.status.eq(revision),
			self._r_frequency.status.eq(frequency),
		]

