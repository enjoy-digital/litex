from migen.fhdl.structure import *
from migen.bus import csr
from migen.bank import description, csrgen
from migen.bank.description import *

from miscope import trigger, recorder

class MiLa:
	def __init__(self, address, trigger, recorder, interface=None):

		self.trigger = trigger
		self.recorder = recorder
		self.interface = interface
		
		self.trig = Signal(self.trigger.trig_w)
		self.dat  = Signal(self.trigger.trig_w)
		
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
			self.trigger.trig.eq(self.trig),
			
			self.recorder.dat.eq(self.dat),
			self.recorder.hit.eq(self.trigger.hit)
		]
		return Fragment(comb)