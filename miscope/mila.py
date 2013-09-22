from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.flow.network import *
from migen.bus import csr
from migen.bank import description, csrgen
from migen.bank.description import *

from miscope.trigger import Trigger
from miscope.storage import Recorder

class MiLa(Module, AutoCSR):
	def __init__(self, width, depth, ports):
		self.width = width

		trigger = Trigger(width, ports)
		recorder = Recorder(width, depth)

		self.submodules.trigger = trigger
		self.submodules.recorder = recorder

		self.sink = trigger.sink

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