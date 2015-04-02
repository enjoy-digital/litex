import math
from collections import OrderedDict

from migen.fhdl.std import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.record import *
from migen.genlib.fsm import FSM, NextState
from migen.genlib.misc import chooser, FlipFlop, Counter, Timeout
from migen.flow.actor import *
from migen.flow.plumbing import Buffer
from migen.actorlib.structuring import Converter, Pipeline
from migen.actorlib.fifo import SyncFIFO, AsyncFIFO
from migen.bank.description import *

eth_mtu = 1532
eth_min_len = 46
eth_interpacket_gap = 12
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
	"ihl":				HField(0,  0, 4),
	"version":			HField(0,  4, 4),
	"total_length":		HField(2,  0, 16),
	"identification":	HField(4,  0, 16),
	"ttl":				HField(8,  0, 8),
	"protocol":			HField(9,  0, 8),
	"checksum":			HField(10,  0, 16),
	"sender_ip":		HField(12,  0, 32),
	"target_ip":		HField(16,  0, 32)
}

icmp_header_len = 8
icmp_header = {
	"msgtype":		HField( 0,  0, 8),
	"code":			HField( 1,  0, 8),
	"checksum":		HField( 2,  0, 16),
	"quench":		HField( 4,  0, 32)
}
icmp_protocol = 0x01

udp_header_len = 8
udp_header = {
	"src_port":		HField( 0,  0, 16),
	"dst_port":		HField( 2,  0, 16),
	"length":		HField( 4,  0, 16),
	"checksum":		HField( 6,  0, 16)
}

udp_protocol = 0x11

etherbone_magic = 0x4e6f
etherbone_version = 1
etherbone_packet_header_len = 8
etherbone_packet_header = {
	"magic":		HField( 0,  0, 16),

	"version":		HField( 2,  4, 4),
	"nr":			HField( 2,  2, 1),
	"pr":			HField( 2,  1, 1),
	"pf":			HField( 2,  0, 1),

	"addr_size":	HField( 3,  4, 4),
	"port_size":	HField( 3,  0, 4)
}

etherbone_record_header_len = 4
etherbone_record_header = {
	"bca":			HField( 0,  0, 1),
	"rca":			HField( 0,  1, 1),
	"rff":			HField( 0,  2, 1),
	"cyc":			HField( 0,  4, 1),
	"wca":			HField( 0,  5, 1),
	"wff":			HField( 0,  6, 1),

	"byte_enable":	HField( 1,  0, 8),

	"wcount":		HField( 2,  0, 8),

	"rcount":		HField( 3,  0, 8)
}

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

def _remove_from_layout(layout, *args):
	r = []
	for f in layout:
		remove = False
		for arg in args:
			if f[0] == arg:
				remove = True
		if not remove:
			r.append(f)
	return r
def eth_phy_description(dw):
	payload_layout = [
		("data", dw),
		("last_be", dw//8),
		("error", dw//8)
	]
	return EndpointDescription(payload_layout, packetized=True)

def eth_mac_description(dw):
	payload_layout = _layout_from_header(mac_header) + [
		("data", dw),
		("last_be", dw//8),
		("error", dw//8)
	]
	return EndpointDescription(payload_layout, packetized=True)

def eth_arp_description(dw):
	param_layout = _layout_from_header(arp_header)
	payload_layout = [
		("data", dw),
		("error", dw//8)
	]
	return EndpointDescription(payload_layout, param_layout, packetized=True)

arp_table_request_layout = [
	("ip_address", 32)
]

arp_table_response_layout = [
	("failed", 1),
	("mac_address", 48)
]

def eth_ipv4_description(dw):
	param_layout = _layout_from_header(ipv4_header)
	payload_layout = [
		("data", dw),
		("error", dw//8)
	]
	return EndpointDescription(payload_layout, param_layout, packetized=True)

def eth_ipv4_user_description(dw):
	param_layout = [
		("length", 16),
		("protocol", 8),
		("ip_address", 32)
	]
	payload_layout = [
		("data", dw),
		("error", dw//8)
	]
	return EndpointDescription(payload_layout, param_layout, packetized=True)

def convert_ip(s):
	ip = 0
	for e in s.split("."):
		ip = ip << 8
		ip += int(e)
	return ip

def eth_icmp_description(dw):
	param_layout = _layout_from_header(icmp_header)
	payload_layout = [
		("data", dw),
		("error", dw//8)
	]
	return EndpointDescription(payload_layout, param_layout, packetized=True)

def eth_icmp_user_description(dw):
	param_layout = _layout_from_header(icmp_header) + [
		("ip_address", 32),
		("length", 16)
	]
	payload_layout = [
		("data", dw),
		("error", dw//8)
	]
	return EndpointDescription(payload_layout, param_layout, packetized=True)

def eth_udp_description(dw):
	param_layout = _layout_from_header(udp_header)
	payload_layout = [
		("data", dw),
		("error", dw//8)
	]
	return EndpointDescription(payload_layout, param_layout, packetized=True)

def eth_udp_user_description(dw):
	param_layout = [
		("src_port", 16),
		("dst_port", 16),
		("ip_address", 32),
		("length", 16)
	]
	payload_layout = [
		("data", dw),
		("error", dw//8)
	]
	return EndpointDescription(payload_layout, param_layout, packetized=True)

def eth_etherbone_packet_description(dw):
	param_layout = _layout_from_header(etherbone_packet_header)
	payload_layout = [
		("data", dw),
		("error", dw//8)
	]
	return EndpointDescription(payload_layout, param_layout, packetized=True)

def eth_etherbone_packet_user_description(dw):
	param_layout = _layout_from_header(etherbone_packet_header)
	param_layout = _remove_from_layout(param_layout, "magic", "portsize", "addrsize", "version")
	param_layout += eth_udp_user_description(dw).param_layout
	payload_layout = [
		("data", dw),
		("error", dw//8)
	]
	return EndpointDescription(payload_layout, param_layout, packetized=True)

def eth_etherbone_record_description(dw):
	param_layout = _layout_from_header(etherbone_record_header)
	payload_layout = [
		("data", dw),
		("error", dw//8)
	]
	return EndpointDescription(payload_layout, param_layout, packetized=True)

def eth_etherbone_mmap_description(dw):
	param_layout = [
		("we", 1),
		("count", 8),
		("base_addr", 32),
		("be", dw//8)
	]
	payload_layout = [
		("addr", 32),
		("data", dw)
	]
	return EndpointDescription(payload_layout, param_layout, packetized=True)

def eth_tty_description(dw):
	payload_layout = [("data", dw)]
	return EndpointDescription(payload_layout, packetized=False)
