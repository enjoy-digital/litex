import re

from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.bank.description import *

def encode_version(version):
	match = re.match("(\d+)\.(\d+)(\.(\d+))?(rc(\d+))?", version, re.IGNORECASE)
	r = (int(match.group(1)) << 12) | (int(match.group(2)) << 8)
	subminor = match.group(4)
	rc = match.group(6)
	if subminor:
		r |= int(subminor) << 4
	if rc:
		r |= int(rc)
	return r

class Identifier(Module, AutoCSR):
	def __init__(self, sysid, version, frequency):
		self._r_sysid = CSRStatus(16)
		self._r_version = CSRStatus(16)
		self._r_frequency = CSRStatus(32)
		
		###

		self.comb += [
			self._r_sysid.status.eq(sysid),
			self._r_version.status.eq(encode_version(version)),
			self._r_frequency.status.eq(frequency)
		]
