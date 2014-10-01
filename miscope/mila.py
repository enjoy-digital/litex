from migen.fhdl.structure import *
from migen.fhdl import verilog
from migen.bank.description import *

from miscope.std import *
from miscope.trigger import Trigger
from miscope.storage import Recorder, RunLengthEncoder

from mibuild.tools import write_to_file

class MiLa(Module, AutoCSR):
	def __init__(self, width, depth, ports, with_rle=False):
		self.width = width
		self.depth = depth
		self.with_rle = with_rle
		self.ports = ports

		self.sink = Record(dat_layout(width))

		self.submodules.trigger = trigger = Trigger(width, ports)
		self.submodules.recorder = recorder = Recorder(width, depth)

		self.comb += [
			self.sink.connect(trigger.sink),
			trigger.source.connect(recorder.trig_sink)
		]

		recorder_dat_source = self.sink
		if with_rle:
			self.submodules.rle = rle = RunLengthEncoder(width)
			self.comb += [
				self.sink.connect(rle.sink),
				rle.source.connect(recorder.dat_sink)
			]
		else:
			self.sink.connect(recorder.dat_sink)

	def export(self, design, layout, filename):
		ret, ns = verilog.convert(design, return_ns=True)
		r = ""
		def format_line(*args):
			return ",".join(args) + "\n"

		r += format_line("config", "width", str(self.width))
		r += format_line("config", "depth", str(self.depth))
		r += format_line("config", "with_rle", str(int(self.with_rle)))

		for e in layout:
			r += format_line("layout", ns.get_name(e), str(flen(e)))
		write_to_file(filename, r)
