from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.flow.network import *
from migen.bus import csr
from migen.bank import description, csrgen
from migen.bank.description import *

class MiLa(Module, AutoCSR):
	def __init__(self, trigger, recorder):
		self.trigger = trigger
		self.recorder = recorder

		self.sink = trigger.sink
		self.submodules += trigger, recorder

		self.comb +=[
			recorder.sink.stb.eq(trigger.source.stb),
			
			recorder.sink.hit.eq(trigger.source.hit),
			trigger.source.ack.eq(recorder.sink.ack)
		]

		# Todo; Insert configurable delay to support pipelined
		# triggers elements
		self.comb +=[
			recorder.sink.dat.eq(self.sink.dat),
		]