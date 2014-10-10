from migen.fhdl.std import *
from migen.fhdl import verilog
from migen.bank.description import *
from migen.actorlib.fifo import AsyncFIFO

from miscope.std import *
from miscope.trigger import Trigger
from miscope.storage import Recorder, RunLengthEncoder

from mibuild.tools import write_to_file

class MiLa(Module, AutoCSR):
	def __init__(self, width, depth, ports, with_rle=False, clk_domain="sys"):
		self.width = width
		self.depth = depth
		self.with_rle = with_rle
		self.ports = ports

		self.sink = Record(dat_layout(width))

		if clk_domain is not "sys":
			fifo = AsyncFIFO([("dat", width)], 32)
			self.submodules += RenameClockDomains(fifo, {"write": clk_domain, "read": "sys"})
			self.comb += [
				fifo.sink.stb.eq(self.sink.stb),
				fifo.sink.dat.eq(self.sink.dat)
			]
			sink = Record(dat_layout(width))
			self.comb += [
				sink.stb.eq(fifo.source.stb),
				sink.dat.eq(fifo.source.dat),
				fifo.source.ack.eq(1)
			]
		else:
			sink = self.sink

		self.submodules.trigger = trigger = Trigger(width, ports)
		self.submodules.recorder = recorder = Recorder(width, depth)
		self.comb += [
			sink.connect(trigger.sink),
			trigger.source.connect(recorder.trig_sink)
		]

		if with_rle:
			self.submodules.rle = rle = RunLengthEncoder(width)
			self.comb += [
				sink.connect(rle.sink),
				rle.source.connect(recorder.dat_sink)
			]
		else:
			self.comb += sink.connect(recorder.dat_sink)

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
