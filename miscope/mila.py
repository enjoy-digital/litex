from migen.fhdl.structure import *
from migen.bank.description import *

from miscope.std import *
from miscope.trigger import Trigger
from miscope.storage import Recorder, RunLengthEncoder

class MiLa(Module, AutoCSR):
	def __init__(self, width, depth, ports, with_rle=False):
		self.width = width
		self.depth = depth
		self.with_rle = with_rle
		self.ports = ports

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

	def get_csv(self, layout):
		r = ""
		def format_line(*args):
			return ",".join(args) + "\n"

		r += format_line("config", "width", str(self.width))
		r += format_line("config", "depth", str(self.depth))
		r += format_line("config", "with_rle", str(int(self.with_rle)))

		for e in layout:
			r += format_line("layout", e.backtrace[-1][0], str(flen(e)))
		return r
