from litescope.common import *
from litescope.core.trigger import LiteScopeTrigger
from litescope.core.storage import LiteScopeRecorder, LiteScopeRunLengthEncoder

from mibuild.tools import write_to_file

class LiteScopeLA(Module, AutoCSR):
	def __init__(self, layout, depth, clk_domain="sys", input_buffer=False, with_rle=False):
		self.layout = layout
		self.data = Cat(*layout)
		self.dw = flen(self.data)
		self.depth = depth
		self.with_rle = with_rle
		self.clk_domain = clk_domain
		self.input_buffer = input_buffer

		self.sink = Sink(data_layout(self.dw))
		self.comb += [
			self.sink.stb.eq(1),
			self.sink.data.eq(self.data)
		]

		self.submodules.trigger = trigger = LiteScopeTrigger(self.dw)
		self.submodules.recorder = recorder = LiteScopeRecorder(self.dw, self.depth)

	def do_finalize(self):
		# insert Buffer on sink (optional, can be used to improve timings)
		if self.input_buffer:
			self.submodules.buffer = Buffer(self.sink.description)
			self.comb += Record.connect(self.sink, self.buffer.d)
			self.sink = self.buffer.q

		# clock domain crossing (optional, required when capture_clk is not sys_clk)
		# XXX : sys_clk must be faster than capture_clk, add Converter on data to remove this limitation
		if self.clk_domain is not "sys":
			self.submodules.fifo = AsyncFIFO(self.sink.description, 32)
			self.submodules += RenameClockDomains(self.fifo, {"write": self.clk_domain, "read": "sys"})
			self.comb += Record.connect(self.sink, self.fifo.sink)
			self.sink = self.fifo.source

		# connect everything
		self.comb += [
			self.trigger.sink.stb.eq(self.sink.stb),
			self.trigger.sink.data.eq(self.sink.data),
			Record.connect(self.trigger.source, self.recorder.trigger_sink)
		]
		if self.with_rle:
			rle = LiteScopeRunLengthEncoder(self.dw)
			self.submodules += rle
			self.comb += [
				Record.connect(self.sink, rle.sink),
				Record.connect(rle.source, self.recorder.data_sink)
			]
		else:
			self.comb += Record.connect(self.sink, self.recorder.data_sink)

	def export(self, vns, filename):
		def format_line(*args):
			return ",".join(args) + "\n"
		r = ""
		r += format_line("config", "dw", str(self.dw))
		r += format_line("config", "depth", str(self.depth))
		r += format_line("config", "with_rle", str(int(self.with_rle)))
		for e in self.layout:
			r += format_line("layout", vns.get_name(e), str(flen(e)))
		write_to_file(filename, r)
