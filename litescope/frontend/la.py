from migen.fhdl.std import *
from migen.fhdl import verilog
from migen.bank.description import *
from migen.actorlib.fifo import AsyncFIFO

from litescope.common import *
from litescope.core.trigger import LiteScopeTrigger
from litescope.core.storage import LiteScopeRecorder, LiteScopeRunLengthEncoder

from mibuild.tools import write_to_file

def _getattr_all(l, attr):
	it = iter(l)
	r = getattr(next(it), attr)
	for e in it:
		if getattr(e, attr) != r:
			raise ValueError
	return r

class LiteScopeLA(Module, AutoCSR):
	def __init__(self, depth, dat, with_rle=False, clk_domain="sys", pipe=False):
		self.depth = depth
		self.with_rle = with_rle
		self.clk_domain = clk_domain
		self.pipe = pipe
		self.ports = []
		self.width = flen(dat)

		self.stb = Signal(reset=1)
		self.dat = dat

	def add_port(self, port_class):
		port = port_class(self.width)
		self.ports.append(port)

	def do_finalize(self):
		stb = self.stb
		dat = self.dat
		if self.pipe:
			sync = getattr(self.sync, self.clk_domain)
			stb_new = Signal()
			dat_new = Signal(flen(dat))
			sync += [
				stb_new.eq(stb),
				dat_new.eq(dat)
			]
			stb = stb_new
			dat = dat_new

		if self.clk_domain is not "sys":
			fifo = AsyncFIFO([("dat", self.width)], 32)
			self.submodules += RenameClockDomains(fifo, {"write": self.clk_domain, "read": "sys"})
			self.comb += [
				fifo.sink.stb.eq(stb),
				fifo.sink.dat.eq(dat)
			]
			sink = Record(dat_layout(self.width))
			self.comb += [
				sink.stb.eq(fifo.source.stb),
				sink.dat.eq(fifo.source.dat),
				fifo.source.ack.eq(1)
			]
		else:
			sink = Record(dat_layout(self.width))
			self.comb += [
				sink.stb.eq(stb),
				sink.dat.eq(dat)
			]

		self.submodules.trigger = trigger = LiteScopeTrigger(self.width, self.ports)
		self.submodules.recorder = recorder = LiteScopeRecorder(self.width, self.depth)
		self.comb += [
			sink.connect(trigger.sink),
			trigger.source.connect(recorder.trig_sink)
		]

		if self.with_rle:
			self.submodules.rle = rle = LiteScopeRunLengthEncoder(self.width)
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
