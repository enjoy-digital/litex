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

class Identifier(Module, AutoReg):
	def __init__(self, sysid, version, frequency):
		self._r_sysid = RegisterField("sysid", 16, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		self._r_version = RegisterField("version", 16, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		self._r_frequency = RegisterField("frequency", 32, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		
		###

		self.comb += [
			self._r_sysid.field.w.eq(sysid),
			self._r_version.field.w.eq(encode_version(version)),
			self._r_frequency.field.w.eq(frequency)
		]
