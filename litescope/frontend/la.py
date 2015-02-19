from litescope.common import *
from litescope.core.trigger import LiteScopeTrigger
from litescope.core.storage import LiteScopeSubSampler, LiteScopeRecorder, LiteScopeRunLengthEncoder

from mibuild.tools import write_to_file

class LiteScopeLA(Module, AutoCSR):
	def __init__(self, layout, depth, clk_domain="sys",
			with_input_buffer=False,
			with_rle=False, rle_length=256,
			with_subsampler=False):
		self.layout = layout
		self.data = Cat(*layout)
		self.dw = flen(self.data)
		if with_rle:
			self.dw += 1
		self.depth = depth
		self.clk_domain = clk_domain
		self.with_rle = with_rle
		self.rle_length = rle_length
		self.with_input_buffer = with_input_buffer
		self.with_subsampler = with_subsampler

		self.sink = Sink(data_layout(self.dw))
		self.comb += [
			self.sink.stb.eq(1),
			self.sink.data.eq(self.data)
		]

		self.submodules.trigger = trigger = LiteScopeTrigger(self.dw)
		self.submodules.recorder = recorder = LiteScopeRecorder(self.dw, self.depth)

	def do_finalize(self):
		sink = self.sink
		# insert Buffer on sink (optional, can be used to improve timings)
		if self.with_input_buffer:
			self.submodules.buffer = Buffer(self.sink.description)
			self.comb += Record.connect(sink, self.buffer.d)
			sink = self.buffer.q

		# clock domain crossing (optional, required when capture_clk is not sys_clk)
		# XXX : sys_clk must be faster than capture_clk, add Converter on data to remove this limitation
		if self.clk_domain is not "sys":
			self.submodules.fifo = AsyncFIFO(self.sink.description, 32)
			self.submodules += RenameClockDomains(self.fifo, {"write": self.clk_domain, "read": "sys"})
			self.comb += Record.connect(sink, self.fifo.sink)
			sink = self.fifo.source

		# connect trigger
		self.comb += [
			self.trigger.sink.stb.eq(sink.stb),
			self.trigger.sink.data.eq(sink.data),
		]

		# insert subsampler (optional)
		if self.with_subsampler:
			self.submodules.subsampler = LiteScopeSubSampler(self.dw)
			self.comb += Record.connect(sink, self.subsampler.sink)
			sink = self.subsampler.source

		# connect recorder
		self.comb += Record.connect(self.trigger.source, self.recorder.trigger_sink)
		if self.with_rle:
			self.submodules.rle = LiteScopeRunLengthEncoder(self.dw, self.rle_length)
			self.comb += [
				Record.connect(sink, self.rle.sink),
				Record.connect(self.rle.source, self.recorder.data_sink),
				self.rle.external_enable.eq(self.recorder.post_hit)
			]
		else:
			self.submodules.delay_buffer = Buffer(self.sink.description)
			self.comb += [
				Record.connect(sink, self.delay_buffer.d),
				Record.connect(self.delay_buffer.q, self.recorder.data_sink)
			]

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
