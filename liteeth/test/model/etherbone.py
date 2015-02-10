import math, copy

from liteeth.common import *
from liteeth.test.common import *

from liteeth.test.model import udp

def print_etherbone(s):
	print_with_prefix(s, "[ETHERBONE]")

# Etherbone model
class EtherboneWrite:
	def __init__(self, data):
		self.data = data

	def __repr__(self):
		return "Write data : {}".format(self.data)


class EtherboneRead:
	def __init__(self, addr):
		self.addr = addr

	def __repr__(self):
		return "Read addr : {}".format(self.addr)

class EtherboneWrites(Packet):
	def __init__(self, init=[], base_addr=0):
		Packet.__init__(self, init)
		self.base_addr = base_addr
		self.writes = []

	def add(self, write):
		self.writes.append(write)

	def encode(self):
		for byte in split_bytes(self.base_addr, 4):
			self.append(byte)
		for write in self.writes:
			for byte in split_bytes(write.data, 4):
				self.append(byte)

	def decode(self):
		base_addr = []
		for i in range(4):
			base_addr.append(self.pop(0))
		self.base_addr = merge_bytes(base_addr)
		self.writes = []
		while len(self) != 0:
			write = []
			for i in range(4):
				write.append(self.pop(0))
			self.writes.append(EtherboneWrite(merge_bytes(write)))

class EtherboneReads(Packet):
	def __init__(self, init=[], base_ret_addr=0):
		Packet.__init__(self, init)
		self.base_ret_addr = base_ret_addr
		self.reads = []

	def add(self, read):
		self.reads.append(read)

	def encode(self):
		for byte in split_bytes(self.base_ret_addr, 4):
			self.append(byte)
		for read in self.reads:
			for byte in split_bytes(read.addr, 4):
				self.append(byte)

	def decode(self):
		base_ret_addr = []
		for i in range(4):
			base_ret_addr.append(self.pop(0))
		self.base_ret_addr = merge_bytes(base_ret_addr)
		self.reads = []
		while len(self) != 0:
			read = []
			for i in range(4):
				read.append(self.pop(0))
			self.reads.append(EtherboneRead(merge_bytes(read)))

class EtherboneRecord(Packet):
	def __init__(self, init=[]):
		Packet.__init__(self, init)
		self.writes = None
		self.reads = None

	def get_writes(self):
		if self.wcount == 0:
			return None
		else:
			writes = []
			for i in range((self.wcount+1)*4):
				writes.append(self.pop(0))
			return EtherboneWrites(writes)

	def get_reads(self):
		if self.rcount == 0:
			return None
		else:
			reads = []
			for i in range((self.rcount+1)*4):
				reads.append(self.pop(0))
			return EtherboneReads(reads)

	def decode(self):
		header = []
		for byte in self[:etherbone_record_header_len]:
			header.append(self.pop(0))
		for k, v in sorted(etherbone_record_header.items()):
			setattr(self, k, get_field_data(v, header))

	def set_writes(self, writes):
		self.writes = writes
		writes.encode()
		for byte in writes:
			self.append(byte)
		self.wcount = len(writes)-4

	def set_reads(self, reads):
		self.reads = reads
		reads.encode()
		for byte in reads:
			self.append(byte)
		self.rcount = len(reads)-4

	def encode(self):
		header = 0
		for k, v in sorted(etherbone_record_header.items()):
			value = merge_bytes(split_bytes(getattr(self, k), math.ceil(v.width/8)), "little")
			header += (value << v.offset+(v.byte*8))
		for d in split_bytes(header, etherbone_record_header_len):
			self.insert(0, d)

	def __repr__(self):
		r = "--------\n"
		for k in sorted(etherbone_record_header.keys()):
			r += k + " : 0x%x" %getattr(self,k) + "\n"
		r += "payload: "
		for d in self:
			r += "%02x" %d
		return r

class EtherbonePacket(Packet):
	def __init__(self, init=[]):
		Packet.__init__(self, init)

	def get_records(self):
		records = []
		done = False
		payload = self
		while len(payload) != 0:
			record = EtherboneRecord(payload)
			record.decode()
			records.append(copy.deepcopy(record))
			writes = record.get_writes()
			reads = record.get_reads()
			payload = record
		return records

	def decode(self):
		header = []
		for byte in self[:etherbone_header_len]:
			header.append(self.pop(0))
		for k, v in sorted(etherbone_header.items()):
			setattr(self, k, get_field_data(v, header))

	def set_records(self, records):
		self.records = records
		for record in records:
			for byte in record:
				self.append(byte)

	def encode(self):
		header = 0
		for k, v in sorted(etherbone_header.items()):
			value = merge_bytes(split_bytes(getattr(self, k), math.ceil(v.width/8)), "little")
			header += (value << v.offset+(v.byte*8))
		for d in split_bytes(header, etherbone_header_len):
			self.insert(0, d)

	def __repr__(self):
		r = "--------\n"
		for k in sorted(etherbone_header.keys()):
			r += k + " : 0x%x" %getattr(self,k) + "\n"
		r += "payload: "
		for d in self:
			r += "%02x" %d
		return r

class Etherbone(Module):
	def  __init__(self, udp, debug=False):
		self.udp = udp
		self.debug = debug
		self.tx_packets = []
		self.tx_packet = EtherbonePacket()
		self.rx_packet = EtherbonePacket()

		self.udp.set_etherbone_callback(self.callback)

	def send(self, packet):
		packet.encode()
		if self.debug:
			print_etherbone(">>>>>>>>")
			print_etherbone(packet)
		udp_packet = udp.UDPPacket(packet)
		udp_packet.src_port = 0x1234
		udp_packet.dst_port = 0x5678
		udp_packet.length = len(packet)
		udp_packet.checksum = 0
		self.udp.send(udp_packet)

	def callback(self, packet):
		packet = Etherbone(packet)
		packet.decode()
		if self.debug:
			print_etherbone("<<<<<<<<")
			print_etherbone(packet)
		self.process(packet)

	def process(self, packet):
		pass

if __name__ == "__main__":
	# Writes/Reads
	writes = EtherboneWrites(base_addr=0x1000)
	for i in range(16):
		writes.add(EtherboneWrite(i))
	reads = EtherboneReads(base_ret_addr=0x2000)
	for i in range(16):
		reads.add(EtherboneRead(i))

	# Record
	record = EtherboneRecord()
	record.set_writes(writes)
	record.set_reads(reads)
	record.bca = 0
	record.rca = 0
	record.rff = 0
	record.cyc = 0
	record.wca = 0
	record.wff = 0
	record.byte_enable = 0
	record.wcount = 16
	record.rcount = 16
	record.encode()

	# Packet
	packet = EtherbonePacket()
	packet.set_records([record for i in range(8)])
	packet.magic = etherbone_magic
	packet.version = etherbone_version
	packet.nr = 0
	packet.pr = 0
	packet.pf = 0
	packet.addr_size = 32//8
	packet.port_size = 32//8
	#print(packet)
	packet.encode()

	# Send packet over UDP to check against Wireshark dissector
	import socket
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.sendto(bytes(packet), ("192.168.1.1", 20000))

	packet = EtherbonePacket(packet)
	packet.decode()
	#print(packet)

	# Record
	records = packet.get_records()
	for record in records:
		writes = record.get_writes()
		writes.decode()
		print(writes.base_addr)
		for e in writes.writes:
			print(e)
		reads = record.get_reads()
		reads.decode()
		print(reads.base_ret_addr)
		for e in reads.reads:
			print(e)
