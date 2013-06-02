from migen.fhdl.structure import *
from migen.bus import csr
from migen.bank import description, csrgen
from migen.bank.description import *

from miscope import trigger, recorder
from miscope.tools.misc import *

class MiLa:
	def __init__(self, address, trigger, recorder, interface=None, trig_is_dat=False):

		self.trigger = trigger
		self.recorder = recorder
		self.interface = interface
		self.trig_is_dat = trig_is_dat
		
		self.stb = Signal(reset=1)
		self.trig = Signal(self.trigger.width)
		self.dat  = Signal(self.recorder.width)
		
		self.set_address(address)
		self.set_interface(interface)

	def set_address(self, address):
		self.address = address
		self.trigger.set_address(self.address)
		self.recorder.set_address(self.address + 0x01)

	def set_interface(self, interface):
		self.interface = interface
		self.trigger.set_interface(interface)
		self.recorder.set_interface(interface)
		
	def get_fragment(self):
		comb =[
			self.recorder.stb.eq(self.stb),
			self.trigger.trig.eq(self.trig),
			
			self.recorder.hit.eq(self.trigger.hit)
		]
		if self.trig_is_dat:
			comb +=[
			self.recorder.dat.eq(self.trig),
			]
		else:
			self.recorder.dat.eq(self.dat),
		
		return Fragment(comb)