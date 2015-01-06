import subprocess
import math

from lib.sata.common import *
from lib.sata.test.common import *

def print_with_prefix(s, prefix=""):
	if not isinstance(s, str):
		s = s.__repr__()
	s = s.split("\n")
	for l in s:
		print(prefix + l)

# PHY Layer model
class PHYDword:
	def __init__(self, dat=0):
		self.dat = dat
		self.start = 1
		self.done = 0

class PHYSource(Module):
	def __init__(self):
		self.source = Source(phy_description(32))
		###
		self.dword = PHYDword()

	def send(self, dword):
		self.dword = dword

	def do_simulation(self, selfp):
		selfp.source.stb = 1
		selfp.source.charisk = 0b0000
		for k, v in primitives.items():
			if v == self.dword.dat:
				selfp.source.charisk = 0b0001
		selfp.source.data = self.dword.dat

class PHYSink(Module):
	def __init__(self):
		self.sink = Sink(phy_description(32))
		###
		self.dword = PHYDword()

	def receive(self):
		self.dword.done = 0
		while self.dword.done == 0:
			yield

	def do_simulation(self, selfp):
		self.dword.done = 0
		selfp.sink.ack = 1
		if selfp.sink.stb == 1:
			self.dword.done = 1
			self.dword.dat = selfp.sink.data

class PHYLayer(Module):
	def __init__(self):

		self.rx = PHYSink()
		self.tx = PHYSource()

		self.source = self.tx.source
		self.sink = self.rx.sink

	def send(self, dword):
		packet = PHYDword(dword)
		self.tx.send(packet)

	def receive(self):
		yield from self.rx.receive()

	def __repr__(self):
		receiving = "%08x " %self.rx.dword.dat
		receiving += decode_primitive(self.rx.dword.dat)
		receiving += " "*(16-len(receiving))

		sending = "%08x " %self.tx.dword.dat
		sending += decode_primitive(self.tx.dword.dat)
		sending += " "*(16-len(sending))

		return receiving + sending

# Link Layer model
def print_link(s):
	print_with_prefix(s, "[LNK]: ")

def import_scrambler_datas():
	with subprocess.Popen(["./scrambler"], stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
		process.stdin.write("0x10000".encode("ASCII"))
		out, err = process.communicate()
	return [int(e, 16) for e in out.decode("utf-8").split("\n")[:-1]]

class LinkPacket(list):
	def __init__(self, init=[]):
		self.ongoing = False
		self.done = False
		self.scrambled_datas = import_scrambler_datas()
		for dword in init:
			self.append(dword)

class LinkRXPacket(LinkPacket):
	def descramble(self):
		for i in range(len(self)):
			self[i] = self[i] ^ self.scrambled_datas[i]

	def check_crc(self):
		stdin = ""
		for v in self[:-1]:
			stdin += "0x%08x " %v
		stdin += "exit"
		with subprocess.Popen("./crc", stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
			process.stdin.write(stdin.encode("ASCII"))
			out, err = process.communicate()
		crc = int(out.decode("ASCII"), 16)
		r = (self[-1] == crc)
		self.pop()
		return r

	def decode(self):
		self.descramble()
		return self.check_crc()

class LinkTXPacket(LinkPacket):
	def insert_crc(self):
		stdin = ""
		for v in self:
			stdin += "0x%08x " %v
		stdin += "exit"
		with subprocess.Popen("./crc", stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
			process.stdin.write(stdin.encode("ASCII"))
			out, err = process.communicate()
		crc = int(out.decode("ASCII"), 16)
		self.append(crc)

	def scramble(self):
		for i in range(len(self)):
			self[i] = self[i] ^ self.scrambled_datas[i]

	def encode(self):
		self.insert_crc()
		self.scramble()

class LinkLayer(Module):
	def  __init__(self, phy, debug=False, random_level=0):
		self.phy = phy
		self.debug = debug
		self.random_level = random_level
		self.tx_packets = []
		self.tx_packet = LinkTXPacket()
		self.rx_packet = LinkRXPacket()

		self.rx_cont = False
		self.rx_last = 0
		self.tx_cont = False
		self.tx_cont_nb = -1
		self.tx_lasts = [0, 0, 0]

		self.scrambled_datas = import_scrambler_datas()

		self.transport_callback = None

		self.send_state = ""
		self.send_states = ["RDY", "SOF", "DATA", "EOF", "WTRM"]

	def set_transport_callback(self, callback):
		self.transport_callback = callback

	def send(self, dword):
		if self.send_state == "RDY":
			self.phy.send(primitives["X_RDY"])
			if dword == primitives["R_RDY"]:
				self.send_state = "SOF"
		elif self.send_state == "SOF":
			self.phy.send(primitives["SOF"])
			self.send_state = "DATA"
		elif self.send_state == "DATA":
			if dword == primitives["HOLD"]:
				self.phy.send(primitives["HOLDA"])
			else:
				self.phy.send(self.tx_packet.pop(0))
				if len(self.tx_packet) == 0:
					self.send_state = "EOF"
		elif self.send_state == "EOF":
			self.phy.send(primitives["EOF"])
			self.send_state = "WTRM"
		elif self.send_state == "WTRM":
			self.phy.send(primitives["WTRM"])
			if dword == primitives["R_OK"]:
				self.tx_packet.done = True
			elif dword == primitives["R_ERR"]:
				self.tx_packet.done = True
			if self.tx_packet.done:
				self.phy.send(primitives["SYNC"])

	def insert_cont(self):
		self.tx_lasts.pop(0)
		self.tx_lasts.append(self.phy.tx.dword.dat)
		self.tx_cont = True
		for i in range(3):
			if not is_primitive(self.tx_lasts[i]):
				self.tx_cont = False
			if self.tx_lasts[i] != self.tx_lasts[0]:
				self.tx_cont = False
		if self.tx_cont:
			if self.tx_cont_nb == 0:
				self.phy.send(primitives["CONT"])
			else:
				self.phy.send(self.scrambled_datas[self.tx_cont_nb])
			self.tx_cont_nb += 1
		else:
			self.tx_cont_nb = 0

	def remove_cont(self, dword):
		if dword == primitives["HOLD"]:
			if self.rx_cont:
				self.tx_lasts = [0, 0, 0]
		if dword == primitives["CONT"]:
			self.rx_cont = True
		elif is_primitive(dword):
			self.rx_last = dword
			self.rx_cont = False
		if self.rx_cont:
			dword = self.rx_last
		return dword

	def callback(self, dword):
		if dword == primitives["X_RDY"]:
			self.phy.send(primitives["R_RDY"])
		elif dword == primitives["WTRM"]:
			self.phy.send(primitives["R_OK"])
			if self.rx_packet.ongoing:
				self.rx_packet.decode()
				if self.transport_callback is not None:
					self.transport_callback(self.rx_packet)
				self.rx_packet.ongoing = False
		elif dword == primitives["HOLD"]:
			self.phy.send(primitives["HOLDA"])
		elif dword == primitives["EOF"]:
			pass
		elif self.rx_packet.ongoing:
			if dword != primitives["HOLD"]:
				n = randn(100)
				if n < self.random_level:
					self.phy.send(primitives["HOLD"])
				else:
					self.phy.send(primitives["R_IP"])
				if not is_primitive(dword):
						self.rx_packet.append(dword)
		elif dword == primitives["SOF"]:
			self.rx_packet = LinkRXPacket()
			self.rx_packet.ongoing = True

	def gen_simulation(self, selfp):
		self.tx_packet.done = True
		self.phy.send(primitives["SYNC"])
		while True:
			yield from self.phy.receive()
			if self.debug:
				print_link(self.phy)
			self.phy.send(primitives["SYNC"])
			rx_dword = self.phy.rx.dword.dat
			rx_dword = self.remove_cont(rx_dword)
			if len(self.tx_packets) != 0:
				if self.tx_packet.done:
					self.tx_packet = self.tx_packets.pop(0)
					self.tx_packet.encode()
					self.send_state = "RDY"
			if not self.tx_packet.done:
				self.send(rx_dword)
			else:
				self.callback(rx_dword)
			self.insert_cont()

# Transport Layer model
def print_transport(s):
	print_with_prefix(s, "[TRN]: ")

def get_field_data(field, packet):
	return (packet[field.dword] >> field.offset) & (2**field.width-1)

class FIS:
	def __init__(self, packet, description, direction="H2D"):
		self.packet = packet
		self.description = description
		self.direction = direction
		self.decode()

	def decode(self):
		for k, v in self.description.items():
			setattr(self, k, get_field_data(v, self.packet))

	def encode(self):
		for k, v in self.description.items():
			self.packet[v.dword] |= (getattr(self, k) << v.offset)

	def __repr__(self):
		if self.direction == "H2D":
			r = ">>>>>>>>\n"
		else:
			r = "<<<<<<<<\n"
		for k in sorted(self.description.keys()):
			r += k + " : 0x%x" %getattr(self,k) + "\n"
		return r

class FIS_REG_H2D(FIS):
	def __init__(self, packet=[0]*fis_reg_h2d_cmd_len):
		FIS.__init__(self, packet, fis_reg_h2d_layout)
		self.type = fis_types["REG_H2D"]
		self.direction = "H2D"

	def __repr__(self):
		r = "FIS_REG_H2D\n"
		r += FIS.__repr__(self)
		return r

class FIS_REG_D2H(FIS):
	def __init__(self, packet=[0]*fis_reg_d2h_cmd_len):
		FIS.__init__(self, packet, fis_reg_d2h_layout)
		self.type = fis_types["REG_D2H"]
		self.direction = "D2H"

	def __repr__(self):
		r = "FIS_REG_D2H\n"
		r += FIS.__repr__(self)
		return r

class FIS_DMA_ACTIVATE_D2H(FIS):
	def __init__(self, packet=[0]*fis_dma_activate_d2h_cmd_len):
		FIS.__init__(self, packet, fis_dma_activate_d2h_layout)
		self.type = fis_types["DMA_ACTIVATE_D2H"]
		self.direction = "D2H"

	def __repr__(self):
		r = "FIS_DMA_ACTIVATE_D2H\n"
		r += FIS.__repr__(self)
		return r

class FIS_DATA(FIS):
	def __init__(self, packet=[0], direction="H2D"):
		FIS.__init__(self, packet, fis_data_layout, direction)
		self.type = fis_types["DATA"]

	def __repr__(self):
		r = "FIS_DATA\n"
		r += FIS.__repr__(self)
		for data in self.packet[1:]:
			r += "%08x\n" %data
		return r

class FIS_UNKNOWN(FIS):
	def __init__(self, packet=[0], direction="H2D"):
		FIS.__init__(self, packet, {}, direction)

	def __repr__(self):
		r = "UNKNOWN\n"
		if self.direction == "H2D":
			r += ">>>>>>>>\n"
		else:
			r += "<<<<<<<<\n"
		for dword in self.packet:
			r += "%08x\n" %dword
		return r

class TransportLayer(Module):
	def __init__(self, link, debug=False, loopback=False):
		self.link = link
		self.debug = debug
		self.loopback = loopback
		self.link.set_transport_callback(self.callback)

	def set_command_callback(self, callback):
		self.command_callback = callback

	def send(self, fis):
		fis.encode()
		packet = LinkTXPacket(fis.packet)
		self.link.tx_packets.append(packet)
		if self.debug and not self.loopback:
			print_transport(fis)

	def callback(self, packet):
		fis_type = packet[0] & 0xff
		if fis_type == fis_types["REG_H2D"]:
			fis = FIS_REG_H2D(packet)
		elif fis_type == fis_types["REG_D2H"]:
			fis = FIS_REG_D2H(packet)
		elif fis_type == fis_types["DMA_ACTIVATE_D2H"]:
			fis = FIS_DMA_ACTIVATE_D2H(packet)
		elif fis_type == fis_types["DATA"]:
			fis = FIS_DATA(packet, direction="H2D")
		else:
			fis = FIS_UNKNOWN(packet, direction="H2D")
		if self.debug:
			print_transport(fis)
		if self.loopback:
			self.send(fis)
		else:
			self.command_callback(fis)

# Command Layer model
class CommandLayer(Module):
	def __init__(self, transport):
		self.transport = transport
		self.transport.set_command_callback(self.callback)

		self.hdd = None

	def set_hdd(self, hdd):
		self.hdd = hdd

	def callback(self, fis):
		resp = None
		if isinstance(fis, FIS_REG_H2D):
			if fis.command == regs["WRITE_DMA_EXT"]:
				resp =  self.hdd.write_dma_callback(fis)
			elif fis.command == regs["READ_DMA_EXT"]:
				resp = self.hdd.read_dma_callback(fis)
		elif isinstance(fis, FIS_DATA):
			resp = self.hdd.data_callback(fis)

		if resp is not None:
			for packet in resp:
				self.transport.send(packet)

# HDD model
def print_hdd(s):
	print_with_prefix(s, "[HDD]: ")

class HDDMemRegion:
	def __init__(self, base, count, sector_size):
		self.base = base
		self.count = count
		self.data = [0]*(count*sector_size//4)

class HDD(Module):
	def __init__(self,
			link_debug=False, link_random_level=0,
			transport_debug=False, transport_loopback=False,
			hdd_debug=False,
			):
		###
		self.phy = PHYLayer()
		self.link = LinkLayer(self.phy, link_debug, link_random_level)
		self.transport = TransportLayer(self.link, transport_debug, transport_loopback)
		self.command = CommandLayer(self.transport)

		self.command.set_hdd(self)

		self.debug = hdd_debug
		self.mem = None
		self.wr_sector = 0
		self.wr_end_sector = 0
		self.rd_sector = 0
		self.rx_end_sector = 0

	def malloc(self, sector, count):
		if self.debug:
			s = "Allocating {n} sectors: {s} to {e}".format(n=count, s=sector, e=sector+count)
			s += " ({} KB)".format(count*logical_sector_size//1024)
			print_hdd(s)
		self.mem = HDDMemRegion(sector, count, logical_sector_size)

	def write(self, sector, data):
		n = math.ceil(dwords2sectors(len(data)))
		if self.debug:
			if n == 1:
				s = "{}".format(sector)
			else:
				s = "{s} to {e}".format(s=sector, e=sector+n-1)
			print_hdd("Writing sector " + s)
		for i in range(len(data)):
			offset = sectors2dwords(sector)
			self.mem.data[offset+i] = data[i]

	def read(self, sector, count):
		if self.debug:
			if count == 1:
				s = "{}".format(sector)
			else:
				s = "{s} to {e}".format(s=sector, e=sector+count-1)
			print_hdd("Reading sector " + s)
		data = []
		for i in range(sectors2dwords(count)):
			data.append(self.mem.data[sectors2dwords(sector)+i])
		return data

	def write_dma_callback(self, fis):
		self.wr_sector = fis.lba_lsb + (fis.lba_msb << 32)
		self.wr_end_sector = self.wr_sector + fis.count
		return [FIS_DMA_ACTIVATE_D2H()]

	def read_dma_callback(self, fis):
		self.rd_sector = fis.lba_lsb + (fis.lba_msb << 32)
		self.rd_end_sector = self.rd_sector + fis.count
		packets = []
		while self.rd_sector != self.rd_end_sector:
			count = min(self.rd_end_sector-self.rd_sector, (fis_max_dwords*4)//logical_sector_size)
			packet = self.read(self.rd_sector, count)
			packet.insert(0, 0)
			packets.append(FIS_DATA(packet, direction="D2H"))
			self.rd_sector += count
		packets.append(FIS_REG_D2H())
		return packets

	def data_callback(self, fis):
		self.write(self.wr_sector, fis.packet[1:])
		self.wr_sector += dwords2sectors(len(fis.packet[1:]))
		if self.wr_sector == self.wr_end_sector:
			return [FIS_REG_D2H()]
		else:
			return [FIS_DMA_ACTIVATE_D2H()]
