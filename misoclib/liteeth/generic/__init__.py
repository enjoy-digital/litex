from misoclib.liteeth.common import *

# Generic classes
class Port:
	def connect(self, port):
		r = [
			Record.connect(self.source, port.sink),
			Record.connect(port.source, self.sink)
		]
		return r

# Generic modules
@DecorateModule(InsertReset)
@DecorateModule(InsertCE)
class FlipFlop(Module):
	def __init__(self, *args, **kwargs):
		self.d = Signal(*args, **kwargs)
		self.q = Signal(*args, **kwargs)
		self.sync += self.q.eq(self.d)

@DecorateModule(InsertReset)
@DecorateModule(InsertCE)
class Counter(Module):
	def __init__(self, signal=None, **kwargs):
		if signal is None:
			self.value = Signal(**kwargs)
		else:
			self.value = signal
		self.width = flen(self.value)
		self.sync += self.value.eq(self.value+1)

@DecorateModule(InsertReset)
@DecorateModule(InsertCE)
class Timeout(Module):
	def __init__(self, length):
		self.reached = Signal()
		###
		value = Signal(max=length)
		self.sync += If(~self.reached, value.eq(value+1))
		self.comb += self.reached.eq(value == (length-1))

class BufferizeEndpoints(ModuleDecorator):
	def __init__(self, submodule, *args):
		ModuleDecorator.__init__(self, submodule)

		endpoints = get_endpoints(submodule)
		sinks = {}
		sources = {}
		for name, endpoint in endpoints.items():
			if name in args or len(args) == 0:
				if isinstance(endpoint, Sink):
					sinks.update({name : endpoint})
				elif isinstance(endpoint, Source):
					sources.update({name : endpoint})

		# add buffer on sinks
		for name, sink in sinks.items():
			buf = Buffer(sink.description)
			self.submodules += buf
			setattr(self, name, buf.d)
			self.comb += Record.connect(buf.q, sink)

		# add buffer on sources
		for name, source in sources.items():
			buf = Buffer(source.description)
			self.submodules += buf
			self.comb += Record.connect(source, buf.d)
			setattr(self, name, buf.q)

class EndpointPacketStatus(Module):
	def __init__(self, endpoint):
		self.start = Signal()
		self.done = Signal()
		self.ongoing = Signal()

		ongoing = Signal()
		self.comb += [
			self.start.eq(endpoint.stb & endpoint.sop & endpoint.ack),
			self.done.eq(endpoint.stb & endpoint.eop & endpoint.ack)
		]
		self.sync += \
			If(self.start,
				ongoing.eq(1)
			).Elif(self.done,
				ongoing.eq(0)
			)
		self.comb += self.ongoing.eq((self.start | ongoing) & ~self.done)

class PacketBuffer(Module):
	def __init__(self, description, data_depth, cmd_depth=4, almost_full=None):
		self.sink = sink = Sink(description)
		self.source = source = Source(description)

		###
		sink_status = EndpointPacketStatus(self.sink)
		source_status = EndpointPacketStatus(self.source)
		self.submodules += sink_status, source_status

		# store incoming packets
		# cmds
		def cmd_description():
			layout = [("error", 1)]
			return EndpointDescription(layout)
		cmd_fifo = SyncFIFO(cmd_description(), cmd_depth)
		self.submodules += cmd_fifo
		self.comb += cmd_fifo.sink.stb.eq(sink_status.done)
		if hasattr(sink, "error"):
			self.comb += cmd_fifo.sink.error.eq(sink.error)

		# data
		data_fifo = SyncFIFO(description, data_depth, buffered=True)
		self.submodules += data_fifo
		self.comb += [
			Record.connect(self.sink, data_fifo.sink),
			data_fifo.sink.stb.eq(self.sink.stb & cmd_fifo.sink.ack),
			self.sink.ack.eq(data_fifo.sink.ack & cmd_fifo.sink.ack),
		]

		# output packets
		self.fsm = fsm = FSM(reset_state="IDLE")
		self.submodules += fsm
		fsm.act("IDLE",
			If(cmd_fifo.source.stb,
				NextState("SEEK_SOP")
			)
		)
		fsm.act("SEEK_SOP",
			If(~data_fifo.source.sop,
				data_fifo.source.ack.eq(1)
			).Else(
				NextState("OUTPUT")
			)
		)
		if hasattr(source, "error"):
			source_error = self.source.error
		else:
			source_error = Signal()

		fsm.act("OUTPUT",
			Record.connect(data_fifo.source, self.source),
			source_error.eq(cmd_fifo.source.error),
			If(source_status.done,
				cmd_fifo.source.ack.eq(1),
				NextState("IDLE")
			)
		)

		# compute almost full
		if almost_full is not None:
			self.almost_full = Signal()
			self.comb += self.almost_full.eq(data_fifo.fifo.level > almost_full)
