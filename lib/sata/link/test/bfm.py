import subprocess

from migen.fhdl.std import *

from lib.sata.std import *
from lib.sata.link.test.common import *

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

def transport_callback(packet):
	print("----")
	for v in packet:
		print("%08x" %v)
	print("----")

class LinkLayer(Module):
	def  __init__(self, phy, debug, hold_random_level=0):
		self.phy = phy
		self.debug = debug
		self.hold_random_level = hold_random_level
		self.tx_packet = LinkTXPacket()
		self.rx_packet = LinkRXPacket()
		self.rx_cont = False

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
			transport_callback(self.rx_packet)
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

class BFM(Module):
	def __init__(self, dw, debug=False, hold_random_level=0):
		###
		self.submodules.phy = PHYLayer(debug)
		self.submodules.link = LinkLayer(self.phy, debug, hold_random_level)
