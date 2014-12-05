import subprocess

from migen.fhdl.std import *

from lib.sata.std import *
from lib.sata.transport.std import *

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
	def __init__(self, debug):
		self.debug = debug

		self.submodules.rx = PHYSink()
		self.submodules.tx = PHYSource()

		self.source = self.tx.source
		self.sink = self.rx.sink

	def send(self, dword):
		packet = PHYDword(dword)
		self.tx.send(packet)

	def receive(self):
		yield from self.rx.receive()
		if self.debug:
				print(self)

	def __repr__(self):
		receiving = "%08x " %self.rx.dword.dat
		receiving += decode_primitive(self.rx.dword.dat)
		receiving += " "*(16-len(receiving))

		sending = "%08x " %self.tx.dword.dat
		sending += decode_primitive(self.tx.dword.dat)
		sending += " "*(16-len(sending))

		return receiving + sending

class LinkPacket(list):
	def __init__(self):
		self.ongoing = False
		self.scrambled_datas = self.import_scrambler_datas()

	def import_scrambler_datas(self):
		with subprocess.Popen(["./scrambler"], stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
			process.stdin.write("0x10000".encode("ASCII"))
			out, err = process.communicate()
		return [int(e, 16) for e in out.decode("utf-8").split("\n")[:-1]]

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
		self.scramble()
		self.insert_crc()

	def scramble(self):
		for i in range(len(self)):
			self[i] = self[i] ^ self.scrambled_datas[i]

	def insert_crc(self):
		stdin = ""
		for v in self[:-1]:
			stdin += "0x%08x " %v
		stdin += "exit"
		with subprocess.Popen("./crc", stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
			process.stdin.write(stdin.encode("ASCII"))
			out, err = process.communicate()
		crc = int(out.decode("ASCII"), 16)
		self.append(crc)

class LinkLayer(Module):
	def  __init__(self, phy, debug, hold_random_level=0):
		self.phy = phy
		self.debug = debug
		self.hold_random_level = hold_random_level
		self.tx_packet = LinkTXPacket()
		self.rx_packet = LinkRXPacket()
		self.rx_cont = False

		self.transport_callback = None

	def set_transport_callback(self, callback):
		self.transport_callback = callback

	def callback(self, dword):
		if dword == primitives["CONT"]:
			self.rx_cont = True
		elif is_primitive(dword):
			self.rx_cont = False

		if dword == primitives["X_RDY"]:
			self.phy.send(primitives["R_RDY"])

		elif dword == primitives["WTRM"]:
			self.phy.send(primitives["R_OK"])

		elif dword == primitives["HOLD"]:
			self.phy.send(primitives["HOLDA"])

		elif dword == primitives["EOF"]:
			self.rx_packet.decode()
			if self.transport_callback is not None:
				self.transport_callback(self.rx_packet)
			self.rx_packet.ongoing = False

		elif self.rx_packet.ongoing:
			if dword != primitives["HOLD"]:
				n = randn(100)
				if n < self.hold_random_level:
					self.phy.send(primitives["HOLD"])
				else:
					self.phy.send(primitives["R_RDY"])
				if not is_primitive(dword):
					if not self.rx_cont:
						self.rx_packet.append(dword)

		elif dword == primitives["SOF"]:
			self.rx_packet = LinkRXPacket()
			self.rx_packet.ongoing = True

	def send(self, packet):
		pass

	def gen_simulation(self, selfp):
		self.phy.send(primitives["SYNC"])
		while True:
			yield from self.phy.receive()
			self.callback(self.phy.rx.dword.dat)

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
	def __init__(self, packet=[0]*fis_reg_h2d_len):
		FIS.__init__(self, packet,fis_reg_h2d_layout)

	def __repr__(self):
		r = "FIS_REG_H2D\n"
		r += FIS.__repr__(self)
		return r

class FIS_REG_D2H(FIS):
	def __init__(self, packet=[0]*fis_reg_d2h_len):
		FIS.__init__(self, packet,fis_reg_d2h_layout)

	def __repr__(self):
		r = "FIS_REG_D2H\n"
		r += FIS.__repr__(self)
		return r

class FIS_DMA_ACTIVATE_D2H(FIS):
	def __init__(self, packet=[0]*fis_dma_activate_d2h_len):
		FIS.__init__(self, packet,fis_dma_activate_d2h_layout)

	def __repr__(self):
		r = "FIS_DMA_ACTIVATE_D2H\n"
		r += FIS.__repr__(self)
		return r

class FIS_DMA_SETUP(FIS):
	def __init__(self, packet=[0]*fis_dma_setup_len):
		FIS.__init__(self, packet,fis_dma_setup_layout)

	def __repr__(self):
		r = "FIS_DMA_SETUP\n"
		r += FIS.__repr__(self)
		return r

class FIS_DATA(FIS):
	def __init__(self, packet=[0]):
		FIS.__init__(self, packet,fis_data_layout)

	def __repr__(self):
		r = "FIS_DATA\n"
		r += FIS.__repr__(self)
		return r

class FIS_PIO_SETUP_D2H(FIS):
	def __init__(self, packet=[0]*fis_pio_setup_d2h_len):
		FIS.__init__(self, packet,fis_pio_setup_d2h_layout)

	def __repr__(self):
		r = "FIS_PIO_SETUP\n"
		r += FIS.__repr__(self)
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
	def __init__(self, link):
		pass

	def callback(self, packet):
		fis_type = packet[0]
		if fis_type == fis_types["REG_H2D"]:
			fis = FIS_REG_H2D(packet)
		elif fis_type == fis_types["REG_D2H"]:
			fis = FIS_REG_D2H(packet)
		elif fis_type == fis_types["DMA_ACTIVATE_D2H"]:
			fis = FIS_DMA_ACTIVATE_D2H(packet)
		elif fis_type == fis_types["DMA_SETUP"]:
			fis = FIS_SETUP(packet)
		elif fis_type == fis_types["DATA"]:
			fis = FIS_DATA(packet)
		elif fis_type == fis_types["PIO_SETUP_D2H"]:
			fis = FIS_PIO_SETUP_D2H(packet)
		else:
			fis = FIS_UNKNOWN(packet)
		print(fis)

class BFM(Module):
	def __init__(self, dw, debug=False, hold_random_level=0):
		###
		self.submodules.phy = PHYLayer(debug)
		self.submodules.link = LinkLayer(self.phy, debug, hold_random_level)
		self.submodules.transport = TransportLayer(self.link)
		self.link.set_transport_callback(self.transport.callback)
