import binascii

from liteeth.common import *
from liteeth.mac.common import *
from liteeth.test.common import *

def crc32(l):
	crc = []
	crc_bytes = binascii.crc32(bytes(l)).to_bytes(4, byteorder="little")
	for byte in crc_bytes:
		crc.append(int(byte))
	return crc

# MAC model
class MACPacket(list):
	def __init__(self, init=[]):
		self.ongoing = False
		self.done = False
		for byte in init:
			self.append(byte)

class MACRXPacket(MACPacket):
	def check_remove_preamble(self):
		if comp(self[0:8], [0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0xD5]):
			for i in range(8):
				self.pop(0)
			return False
		else:
			return True

	def check_remove_crc(self):
		if comp(self[-4:], crc32(self[:-4])):
			for i in range(4):
				self.pop()
			return False
		else:
			return True

class MACTXPacket(MACPacket):
	def insert_crc(self):
		return self

	def insert_preamble(self):
		return self

class MAC(Module):
	def  __init__(self, phy, debug=False, random_level=0):
		self.phy = phy
		self.debug = debug
		self.random_level = random_level
		self.tx_packets = []
		self.tx_packet = MACTXPacket()
		self.rx_packet = MACRXPacket()

		self.ip_callback = None

	def set_ip_callback(self, callback):
		self.ip_callback = callback

	def send(self, datas):
		tx_packet = MACTXPacket(datas)
		tx_packet.insert_crc()
		tx_packet.insert_preamble()
		self.tx_packets.append(tx_packet)

	def callback(self, datas):
		rx_packet = MACRXPacket(datas)
		preamble_error = rx_packet.check_remove_preamble()
		crc_error = rx_packet.check_remove_crc()
		if (not preamble_error) and (not crc_error):
			if self.ip_callback is not None:
				self.ip_callback(rx_packet)

	def gen_simulation(self, selfp):
		self.tx_packet.done = True
		while True:
			yield from self.phy.receive()
			self.callback(self.phy.packet)
			# XXX add full duplex
			if len(self.tx_packets) != 0:
				tx_packet = self.tx_packets.pop(0)
				yield from self.phy.send(tx_packet)
