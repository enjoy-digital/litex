import math, binascii

from liteeth.common import *
from liteeth.mac.common import *
from liteeth.test.common import *
from liteeth.test.mac import *

def print_arp(s):
	print_with_prefix(s, "[ARP]")

preamble = split_bytes(eth_preamble, 8)

# ARP model
class ARPPacket(Packet):
	def __init__(self, init=[]):
		Packet.__init__(self, init)

	def decode(self):
		header = []
		for byte in self[:arp_header_len]:
			header.append(self.pop(0))
		for k, v in sorted(arp_header.items()):
			setattr(self, k, get_field_data(v, header))

	def encode(self):
		header = 0
		for k, v in sorted(arp_header.items()):
			header |= (getattr(self, k) << (v.byte*8+v.offset))
		for d in reversed(split_bytes(header, arp_header_len)):
			self.insert(0, d)

	def __repr__(self):
		r = "--------\n"
		for k in sorted(arp_header.keys()):
			r += k + " : 0x%x" %getattr(self,k) + "\n"
		r += "payload: "
		for d in self:
			r += "%02x" %d
		return r

class ARP(Module):
	def  __init__(self, mac, ip_address, mac_address, debug=False):
		self.mac = mac
		self.ip_address = ip_address
		self.mac_address = mac_addres
		self.debug = debug
		self.tx_packets = []
		self.tx_packet = ARPPacket()
		self.rx_packet = ARPPacket()
		self.table = {}
		self.request_pending = False

		self.mac.set_arp_callback(self.callback)

	def send(self, packet):
		if self.debug:
			print_arp(">>>>>>>>")
			print_arp(packet)
		packet.encode()
		self.mac.send(MACPacket(packet))

	def callback(self, packet):
		packet = ARPPacket(datas)
		packet.decode()
		if self.debug:
			print_arp("<<<<<<<<")
			print_arp(packet)
		self.process_packet()

	def process(self, packet):
		if len(packet) != arp_packet_length-arp_header_length:
			raise ValueError
		if packet.hardware_type != arp_hwtype_ethernet:
			raise ValueError
		if packet.protocol_type != arp_proto_ip:
			raise ValueError
		if packet.hardware_address_length != 6:
			raise ValueError
		if packet.protocol_address_length != 4:
			raise ValueError
		if packet.operation == arp_opcode_request:
			self.process_request(packet)
		elif packet.operation == arp_opcode_reply:
			self.process_reply(packet)
	
	def process_request(self, request):
		if request.destination_ip_address = self.ip_address:
			reply = ARPPacket([0]*(arp_packet_length-arp_header_length))
			reply.hardware_type = arp_hwtype_ethernet
			reply.protocol_type = arp_proto_ip
			reply.hardware_address_length = 6
			reply.protocol_address_length = 4
			reply.source_mac_address = self.mac_address
			reply.source_ip_address = self.ip_address
			reply.destination_mac_address = request.source_mac_address
			reply.destination_ip_address = request.source_ip_address
			self.send(reply)

	def process_reply(self, reply):
		self.table[reply.source_ip_address] = reply.source_mac_address

	def request(self, ip_address):
		request = ARPPacket([0]*(arp_packet_length-arp_header_length))
		request.hardware_type = arp_hwtype_ethernet
		request.protocol_type = arp_proto_ip
		request.hardware_address_length = 6
		request.protocol_address_length = 4
		request.source_mac_address = self.mac_address
		request.source_ip_address = self.ip_address
		request.destination_mac_address = 0xffffffffffff
		request.destination_ip_address = ip_address
