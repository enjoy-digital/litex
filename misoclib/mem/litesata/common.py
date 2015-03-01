import math

from migen.fhdl.std import *
from migen.fhdl.decorators import ModuleDecorator
from migen.genlib.resetsync import *
from migen.genlib.fsm import *
from migen.genlib.record import *
from migen.genlib.misc import chooser, optree, Counter, Timeout
from migen.genlib.cdc import *
from migen.flow.actor import *
from migen.flow.plumbing import Multiplexer, Demultiplexer
from migen.flow.plumbing import Buffer
from migen.actorlib.fifo import *
from migen.actorlib.structuring import Pipeline, Converter

bitrates = {
	"sata_gen3"	:	6.0,
	"sata_gen2"	:	3.0,
	"sata_gen1"	:	1.5,
}

frequencies = {
	"sata_gen3"	:	150.0,
	"sata_gen2"	:	75.0,
	"sata_gen1"	:	37.5,
}

# PHY / Link Layers
primitives = {
	"ALIGN"	:	0x7B4A4ABC,
	"CONT"	: 	0X9999AA7C,
	"SYNC"	:	0xB5B5957C,
	"R_RDY"	:	0x4A4A957C,
	"R_OK"	:	0x3535B57C,
	"R_ERR"	:	0x5656B57C,
	"R_IP"	:	0X5555B57C,
	"X_RDY"	:	0x5757B57C,
	"CONT"	:	0x9999AA7C,
	"WTRM"	:	0x5858B57C,
	"SOF"	:	0x3737B57C,
	"EOF"	:	0xD5D5B57C,
	"HOLD"	:	0xD5D5AA7C,
	"HOLDA"	: 	0X9595AA7C
}

def is_primitive(dword):
	for k, v in primitives.items():
		if dword == v:
			return True
	return False

def decode_primitive(dword):
	for k, v in primitives.items():
		if dword == v:
			return k
	return ""

def phy_description(dw):
	layout = [
		("data", dw),
		("charisk", dw//8),
	]
	return EndpointDescription(layout, packetized=False)

def link_description(dw):
	layout = [
		("d", dw),
		("error", 1)
	]
	return EndpointDescription(layout, packetized=True)

# Transport Layer
fis_max_dwords = 2048

fis_types = {
	"REG_H2D":          0x27,
	"REG_D2H":          0x34,
	"DMA_ACTIVATE_D2H": 0x39,
	"PIO_SETUP_D2H":	0x5F,
	"DATA":             0x46
}

class FISField():
	def __init__(self, dword, offset, width):
		self.dword = dword
		self.offset = offset
		self.width = width

fis_reg_h2d_cmd_len = 5
fis_reg_h2d_layout = {
	"type":         FISField(0,  0, 8),
	"pm_port":      FISField(0,  8, 4),
	"c":            FISField(0, 15, 1),
	"command":      FISField(0, 16, 8),
	"features_lsb": FISField(0, 24, 8),

	"lba_lsb":      FISField(1, 0, 24),
	"device":       FISField(1, 24, 8),

	"lba_msb":      FISField(2, 0, 24),
	"features_msb": FISField(2, 24, 8),

	"count":        FISField(3, 0, 16),
	"icc":          FISField(3, 16, 8),
	"control":      FISField(3, 24, 8)
}

fis_reg_d2h_cmd_len = 5
fis_reg_d2h_layout = {
	"type":    FISField(0,  0, 8),
	"pm_port": FISField(0,  8, 4),
	"i":       FISField(0, 14, 1),
	"status":  FISField(0, 16, 8),
	"error":   FISField(0, 24, 8),

	"lba_lsb": FISField(1, 0, 24),
	"device":  FISField(1, 24, 8),

	"lba_msb": FISField(2, 0, 24),

	"count":   FISField(3, 0, 16)
}

fis_dma_activate_d2h_cmd_len = 1
fis_dma_activate_d2h_layout = {
	"type":    FISField(0,  0, 8),
	"pm_port": FISField(0,  8, 4)
}

fis_pio_setup_d2h_cmd_len = 5
fis_pio_setup_d2h_layout = {
	"type":    FISField(0,  0, 8),
	"pm_port": FISField(0,  8, 4),
	"d":       FISField(0, 13, 1),
	"i":       FISField(0, 14, 1),
	"status":  FISField(0, 16, 8),
	"error":   FISField(0, 24, 8),

	"lba_lsb": FISField(1, 0, 24),

	"lba_msb": FISField(2, 0, 24),

	"count":   FISField(3, 0, 16),

	"transfer_count":	FISField(4, 0, 16),
}

fis_data_cmd_len = 1
fis_data_layout = {
	"type": FISField(0,  0, 8)
}

def transport_tx_description(dw):
	layout = [
		("type", 8),
		("pm_port", 4),
		("c", 1),
		("command", 8),
		("features", 16),
		("lba", 48),
		("device", 8),
		("count", 16),
		("icc", 8),
		("control", 8),
		("data", dw)
	]
	return EndpointDescription(layout, packetized=True)

def transport_rx_description(dw):
	layout = [
		("type", 8),
		("pm_port", 4),
		("r", 1),
		("d", 1),
		("i", 1),
		("status", 8),
		("errors", 8),
		("lba", 48),
		("device", 8),
		("count", 16),
		("transfer_count", 16),
		("data", dw),
		("error", 1)
	]
	return EndpointDescription(layout, packetized=True)

# Command Layer
regs = {
	"WRITE_DMA_EXT"			: 0x35,
	"READ_DMA_EXT"			: 0x25,
	"IDENTIFY_DEVICE"		: 0xEC
}

reg_d2h_status = {
	"bsy"	:	7,
	"drdy"	:	6,
	"df"	:	5,
	"se"	:	5,
	"dwe"	:	4,
	"drq"	:	3,
	"ae"	:	2,
	"sns"	:	1,
	"cc"	: 	0,
	"err"	:	0
}

def command_tx_description(dw):
	layout = [
		("write", 1),
		("read", 1),
		("identify", 1),
		("sector", 48),
		("count", 16),
		("data", dw)
	]
	return EndpointDescription(layout, packetized=True)

def command_rx_description(dw):
	layout = [
		("write", 1),
		("read", 1),
		("identify", 1),
		("last", 1),
		("failed", 1),
		("data", dw)
	]
	return EndpointDescription(layout, packetized=True)

def command_rx_cmd_description(dw):
	layout = [
		("write", 1),
		("read", 1),
		("identify", 1),
		("last", 1),
		("failed", 1)
	]
	return EndpointDescription(layout, packetized=False)

def command_rx_data_description(dw):
	layout = [
		("data", dw)
	]
	return EndpointDescription(layout, packetized=True)

# HDD
logical_sector_size = 512 # constant since all HDDs use this

def dwords2sectors(n):
	return math.ceil(n*4/logical_sector_size)

def sectors2dwords(n):
	return n*logical_sector_size//4

# Generic modules
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
		self.comb += [
			cmd_fifo.sink.stb.eq(sink_status.done),
			cmd_fifo.sink.error.eq(sink.error)
		]

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
		fsm.act("OUTPUT",
			Record.connect(data_fifo.source, self.source),
			self.source.error.eq(cmd_fifo.source.error),
			If(source_status.done,
				cmd_fifo.source.ack.eq(1),
				NextState("IDLE")
			)
		)

		# compute almost full
		if almost_full is not None:
			self.almost_full = Signal()
			self.comb += self.almost_full.eq(data_fifo.fifo.level > almost_full)
