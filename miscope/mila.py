from migen.fhdl.structure import *
from migen.bank.description import *

from miscope.std import *
from miscope.trigger import Trigger
from miscope.storage import Recorder, RunLengthEncoder

class MiLa(Module, AutoCSR):
	def __init__(self, width, depth, ports, with_rle=False):
		self.width = width

		self.sink = rec_dat(width)

		trigger = Trigger(width, ports)
		recorder = Recorder(width, depth)

		self.submodules.trigger = trigger
		self.submodules.recorder = recorder


		self.comb += [
			self.sink.connect(trigger.sink),
			trigger.source.connect(recorder.trig_sink)
		]

		recorder_dat_source = self.sink
		if with_rle:
			self.submodules.rle = RunLengthEncoder(width)
			self.comb += self.sink.connect(self.rle.sink)
			recorder_dat_source = self.rle.source
		self.comb += recorder_dat_source.connect(recorder.dat_sink)

	def get_csv(self, dat):
		r = ""
		for e in dat:
			r += e.backtrace[-1][0] + "," + str(flen(e)) + "\n"
		return r
