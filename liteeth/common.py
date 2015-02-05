import math
from collections import OrderedDict

from migen.fhdl.std import *
from migen.fhdl.decorators import ModuleDecorator
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.record import *
from migen.genlib.fsm import FSM, NextState
from migen.genlib.misc import chooser
from migen.flow.actor import EndpointDescription
from migen.flow.actor import Sink, Source
from migen.actorlib.structuring import Converter, Pipeline
from migen.actorlib.fifo import SyncFIFO, AsyncFIFO
from migen.bank.description import *

eth_mtu = 1532
eth_preamble = 0xD555555555555555
buffer_depth = 2**log2_int(eth_mtu, need_pow2=False)

class HField():
	def __init__(self, byte, offset, width):
		self.byte = byte
		self.offset = offset
		self.width = width

ethernet_type_ip = 0x800
ethernet_type_arp = 0x806

mac_header_len = 14
mac_header = {
	"target_mac":		HField(0,  0, 48),
	"sender_mac":		HField(6,  0, 48),
	"ethernet_type":	HField(12, 0, 16)
}

arp_packet_length = 60
arp_hwtype_ethernet = 0x0001
arp_proto_ip = 0x0800
arp_opcode_request = 0x0001
arp_opcode_reply = 0x0002

arp_header_len = 28
arp_header = {
	"hwtype":			HField( 0,  0, 16),
	"proto":			HField( 2,  0, 16),
	"hwsize":			HField( 4,  0, 8),
	"protosize":		HField( 5,  0, 8),
	"opcode":			HField( 6,  0, 16),
	"sender_mac":		HField( 8,  0, 48),
	"sender_ip":		HField(14,  0, 32),
	"target_mac":		HField(18,  0, 48),
	"target_ip":		HField(24,  0, 32)
}

ipv4_header_len = 20
ipv4_header = {
	"version":			HField(0,  0, 4),
	"ihl":				HField(0,  4, 4),
	"diff_services":	HField(1,  0, 6),
	"ecn":				HField(1,  6, 2),
	"total_length":		HField(2,  0, 16),
	"identification":	HField(4,  0, 16),
	"flags":			HField(6,  0, 3),
	"fragment_offset":	HField(6,  3, 13),
	"ttl":				HField(8,  0, 8),
	"protocol":			HField(9,  0, 8),
	"checksum":			HField(10,  0, 16),
	"sender_ip":		HField(12,  0, 32),
	"target_ip":		HField(16,  0, 32)
}

udp_header_len = 8
udp_header = {
	"src_port":		HField( 0,  0, 16),
	"dst_port":		HField( 2,  0, 16),
	"length":		HField( 4,  0, 16),
	"checksum":		HField( 6,  0, 16)
}

udp_protocol = 0x11

def reverse_bytes(v):
	n = math.ceil(flen(v)/8)
	r = []
	for i in reversed(range(n)):
		r.append(v[i*8:min((i+1)*8, flen(v))])
	return Cat(iter(r))

# layouts
def _layout_from_header(header):
	_layout = []
	for k, v in sorted(header.items()):
		_layout.append((k, v.width))
	return _layout

def eth_phy_description(dw):
	layout = [
		("data", dw),
		("last_be", dw//8),
		("error", dw//8)
	]
	return EndpointDescription(layout, packetized=True)

def eth_mac_description(dw):
	layout = _layout_from_header(mac_header) + [
		("data", dw),
		("last_be", dw//8),
		("error", dw//8)
	]
	return EndpointDescription(layout, packetized=True)

def eth_arp_description(dw):
	layout = _layout_from_header(arp_header) + [
		("data", dw),
		("error", dw//8)
	]
	return EndpointDescription(layout, packetized=True)

arp_table_request_layout = [
	("ip_address", 32)
]

arp_table_response_layout = [
	("failed", 1),
	("mac_address", 48)
]

def eth_ipv4_description(dw):
	layout = _layout_from_header(ipv4_header) + [
		("data", dw),
		("error", dw//8)
	]
	return EndpointDescription(layout, packetized=True)

def eth_ipv4_user_description(dw):
	layout = [
		("length", 16),
		("protocol", 8),
		("ip_address", 32),
		("data", dw),
		("error", dw//8)
	]
	return EndpointDescription(layout, packetized=True)

def convert_ip(s):
	ip = 0
	for e in s.split("."):
		ip = ip << 8
		ip += int(e)
	return ip

def eth_udp_description(dw):
	layout = _layout_from_header(udp_header) + [
		("data", dw),
		("error", dw//8)
	]
	return EndpointDescription(layout, packetized=True)

def eth_udp_user_description(dw):
	layout = [
		("src_port", 16),
		("dst_port", 16),
		("ip_address", 32),
		("length", 16),
		("data", dw),
		("error", dw//8)
	]
	return EndpointDescription(layout, packetized=True)

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

