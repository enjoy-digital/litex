import subprocess

from migen.fhdl.std import *

from lib.sata.common import *
from lib.sata.test.common import *

class PHYDword:
	def __init__(self, dat=0):
		self.dat = dat
		self.start = 1
		self.done = 0

class PHYSource(Module):
	def __init__(self):
		self.source = Source(phy_layout(32))
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
		self.sink = Sink(phy_layout(32))
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
	def __init__(self, debug=False):
		self.debug = debug

		self.submodules.rx = PHYSink()
		self.submodules.tx = PHYSource()

		self.source = self.tx.source
		self.sink = self.rx.sink

	def send(self, dword):
		packet = PHYDword(dword)
		self.tx.send(packet)

	def receive(self):
		if self.debug:
				print(self)
		yield from self.rx.receive()

	def __repr__(self):
		receiving = "%08x " %self.rx.dword.dat
		receiving += decode_primitive(self.rx.dword.dat)
		receiving += " "*(16-len(receiving))

		sending = "%08x " %self.tx.dword.dat
		sending += decode_primitive(self.tx.dword.dat)
		sending += " "*(16-len(sending))

		return receiving + sending

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
	def decode(self):
		self.descramble()
		return self.check_crc()

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

class LinkTXPacket(LinkPacket):
	def encode(self):
		self.insert_crc()
		self.scramble()

	def scramble(self):
		for i in range(len(self)):
			self[i] = self[i] ^ self.scrambled_datas[i]

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

	def gen_simulation(self, selfp):
		self.tx_packet.done = True
		self.phy.send(primitives["SYNC"])
		while True:
			yield from self.phy.receive()
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

def get_field_data(field, packet):
	return (packet[field.dword] >> field.offset) & (2**field.width-1)

class FIS:
	def __init__(self, packet, layout):
		self.packet = packet
		self.layout = layout
		self.decode()

	def decode(self):
		for k, v in self.layout.items():
			setattr(self, k, get_field_data(v, self.packet))

	def encode(self):
		for k, v in self.layout.items():
			self.packet[v.dword] |= (getattr(self, k) << v.offset)

	def __repr__(self):
		r = "--------\n"
		for k in sorted(self.layout.keys()):
			r += k + " : 0x%x" %getattr(self,k) + "\n"
		return r

class FIS_REG_H2D(FIS):
	def __init__(self, packet=[0]*fis_reg_h2d_cmd_len):
		FIS.__init__(self, packet,fis_reg_h2d_layout)
		self.type = fis_types["REG_H2D"]

	def __repr__(self):
		r = "FIS_REG_H2D\n"
		r += FIS.__repr__(self)
		return r

class FIS_REG_D2H(FIS):
	def __init__(self, packet=[0]*fis_reg_d2h_cmd_len):
		FIS.__init__(self, packet,fis_reg_d2h_layout)
		self.type = fis_types["REG_D2H"]

	def __repr__(self):
		r = "FIS_REG_D2H\n"
		r += FIS.__repr__(self)
		return r

class FIS_DMA_ACTIVATE_D2H(FIS):
	def __init__(self, packet=[0]*fis_dma_activate_d2h_cmd_len):
		FIS.__init__(self, packet,fis_dma_activate_d2h_layout)
		self.type = fis_types["DMA_ACTIVATE_D2H"]

	def __repr__(self):
		r = "FIS_DMA_ACTIVATE_D2H\n"
		r += FIS.__repr__(self)
		return r

class FIS_DATA(FIS):
	def __init__(self, packet=[0]):
		FIS.__init__(self, packet,fis_data_layout)
		self.type = fis_types["DATA"]

	def __repr__(self):
		r = "FIS_DATA\n"
		r += FIS.__repr__(self)
		for data in self.packet[1:]:
			r += "%08x\n" %data
		return r

class FIS_UNKNOWN(FIS):
	def __init__(self, packet=[0]):
		FIS.__init__(self, packet, {})

	def __repr__(self):
		r = "UNKNOWN\n"
		r += "--------\n"
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
			print(fis)

	def callback(self, packet):
		fis_type = packet[0] & 0xff
		if fis_type == fis_types["REG_H2D"]:
			fis = FIS_REG_H2D(packet)
		elif fis_type == fis_types["REG_D2H"]:
			fis = FIS_REG_D2H(packet)
		elif fis_type == fis_types["DMA_ACTIVATE_D2H"]:
			fis = FIS_DMA_ACTIVATE_D2H(packet)
		elif fis_type == fis_types["DATA"]:
			fis = FIS_DATA(packet)
		else:
			fis = FIS_UNKNOWN(packet)
		if self.debug:
			print(fis)
		if self.loopback:
			self.send(fis)
		else:
			self.command_callback(fis)

class CommandLayer(Module):
	def __init__(self, transport, debug=False):
		self.transport = transport
		self.debug = debug
		self.transport.set_command_callback(self.callback)

		self.dma_enable = 0
		self.dma_address = 0

	def allocate_dma(self, base, length):
		self.dma_base = base
		self.dma_buffer = [0]*(length//4)

	def enable_dma(self):
		self.dma_enable = 1

	def disable_dma(self):
		self.dma_enable = 0

	def dma_write(self, adr, data):
		current_adr = (adr-self.dma_base)//4
		for i in range(len(data)):
			self.dma_buffer[current_adr+i] = data[i]

	def dma_read(self, adr, length=1):
		current_adr = (adr-self.dma_base)//4
		data = []
		for i in range(length//4):
			data.append(self.dma_buffer[current_adr+i])
		return data

	def callback(self, fis):
		# XXX maximum of 2048 DWORDS per DMA
		if isinstance(fis, FIS_REG_H2D):
			if fis.command == regs["WRITE_DMA_EXT"]:
				self.dma_address = fis.lba_lsb
				dma_activate = FIS_DMA_ACTIVATE_D2H()
				self.transport.send(dma_activate)
			elif fis.command == regs["READ_DMA_EXT"]:
				self.dma_address = fis.lba_lsb
				data = FIS_DATA(self.dma_read(fis.lba_lsb, fis.count*4))
				self.transport.send(data)
			elif fis.command == regs["IDENTIFY_DEVICE_DMA"]:
				self.dma_address = fis.lba_lsb
				data = FIS_DATA(self.dma_read(fis.lba_lsb, fis.count*4))
				self.transport.send(data)
		elif isinstance(fis, FIS_DATA):
			if self.dma_enable:
				self.dma_write(self.dma_address, fis.packet[1:])
				self.dma_address += len(fis.packet[1:])

class BFM(Module):
	def __init__(self,
			phy_debug=False,
			link_debug=False, link_random_level=0,
			transport_debug=False, transport_loopback=False,
			command_debug=False
			):
		###
		self.submodules.phy = PHYLayer(phy_debug)
		self.submodules.link = LinkLayer(self.phy, link_debug, link_random_level)
		self.submodules.transport = TransportLayer(self.link, transport_debug, transport_loopback)
		self.submodules.command = CommandLayer(self.transport, command_debug)
