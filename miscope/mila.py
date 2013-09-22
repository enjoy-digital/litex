from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.flow.network import *
from migen.bus import csr
from migen.bank import description, csrgen
from migen.bank.description import *

from miscope.std import *
from miscope.trigger import Trigger
from miscope.storage import RunLengthEncoder, Recorder

class MiLa(Module, AutoCSR):
	def __init__(self, width, depth, ports, rle=False):
		self.width = width

		self.sink = rec_dat(width)

		trigger = Trigger(width, ports)
		recorder = Recorder(width, depth)

		self.submodules.trigger = trigger
		self.submodules.recorder = recorder


		self.comb += [

			trigger.sink.stb.eq(self.sink.stb),
			trigger.sink.dat.eq(self.sink.dat),
		
			recorder.trig_sink.stb.eq(trigger.source.stb),
			recorder.trig_sink.hit.eq(trigger.source.hit),
			trigger.source.ack.eq(recorder.trig_sink.ack),

			self.sink.ack.eq(1), #FIXME
		]

		if rle:
			self.submodules.rle = RunLengthEncoder(width, 1024)
			self.comb +=[
				self.rle.sink.stb.eq(self.sink.stb),
				self.rle.sink.dat.eq(self.sink.dat),

				recorder.dat_sink.stb.eq(self.rle.source.stb),
				recorder.dat_sink.dat.eq(self.rle.source.dat),
			]
		else:
			self.comb +=[
				recorder.dat_sink.stb.eq(self.sink.stb),
				recorder.dat_sink.dat.eq(self.sink.dat),
			]