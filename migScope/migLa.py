from migen.fhdl.structure import *
from migen.bus import csr
from migen.bank import description, csrgen
from migen.bank.description import *

import sys
sys.path.append("../")

from migScope import trigger, recorder

class MigLa:
	def __init__(self,address, trig, rec, interface=None):
		self.address = address
		self.trig = trig
		self.rec = rec
		self.interface = interface
		
		self.in_trig = Signal(self.trig.trig_width)
		self.in_dat  = Signal(self.trig.trig_width)
		
		self.trig.set_address(self.address)
		self.rec.set_address(self.address + 0x0200)
		
		self.trig.set_interface(self.interface)
		self.rec.set_interface(self.interface)
	
	def get_fragment(self):
		comb = []
		comb += [
			self.trig.in_trig.eq(self.in_trig),
		]
		comb += [
			self.rec.trig_dat.eq(self.in_dat),
			self.rec.trig_hit.eq(self.trig.hit)
		]
		return Fragment(comb=comb)