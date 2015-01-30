import math, binascii

from liteeth.common import *
from liteeth.mac.common import *
from liteeth.test.common import *

from liteeth.test.model import mac

def print_ip(s):
	print_with_prefix(s, "[IP]")

preamble = split_bytes(eth_preamble, 8)

# IP model
class IPPacket(Packet):
	def __init__(self, init=[]):
		Packet.__init__(self, init)

	def decode(self):
		header = []
		for byte in self[:ipv4_header_len]:
			header.append(self.pop(0))
		for k, v in sorted(ipv4_header.items()):
			setattr(self, k, get_field_data(v, header))

	def encode(self):
		header = 0
		for k, v in sorted(ipv4_header.items()):
			value = merge_bytes(split_bytes(getattr(self, k), math.ceil(v.width/8)), "little")
			header += (value << v.offset+(v.byte*8))
		for d in split_bytes(header, ipv4_header_len):
			self.insert(0, d)

	def __repr__(self):
		r = "--------\n"
		for k in sorted(ipv4_header.keys()):
			r += k + " : 0x%x" %getattr(self,k) + "\n"
		r += "payload: "
		for d in self:
			r += "%02x" %d
		return r

class IP(Module):
	def  __init__(self, mac, mac_address, ip_address, debug=False, loopback=False):
		self.mac = mac
		self.mac_address = mac_address
		self.ip_address = ip_address
		self.debug = debug
		self.loopback = loopback
		self.tx_packets = []
		self.tx_packet = IPPacket()
		self.rx_packet = IPPacket()
		self.table = {}
		self.request_pending = False

		self.mac.set_ip_callback(self.callback)

	def send(self, packet):
		packet.encode()
		if self.debug:
			print_ip(">>>>>>>>")
			print_ip(packet)
		mac_packet = mac.MACPacket(packet)
		mac_packet.destination_mac_address = 0x12345678abcd # XXX
		mac_packet.source_mac_address = self.mac_address
		mac_packet.ethernet_type = ethernet_type_ip
		self.mac.send(mac_packet)

	def callback(self, packet):
		packet = IPPacket(packet)
		packet.decode()
		if self.debug:
			print_ip("<<<<<<<<")
			print_ip(packet)
		if self.loopback:
			self.send(packet)
		else:
			self.process(packet)

	def process(self, packet):
		pass
	
if __name__ == "__main__":
	from liteeth.test.model.dumps import *
	from liteeth.test.model.mac import *
	errors = 0
	# ARP request
	packet = MACPacket(udp)
	packet.decode_remove_header()
	#print(packet)
	packet = IPPacket(packet)
	# check decoding
	packet.decode()
	print(packet)
	errors += verify_packet(packet, {})
	# check encoding
	packet.encode()
	packet.decode()
	#print(packet)
	errors += verify_packet(packet, {})

	print("ip errors " + str(errors))