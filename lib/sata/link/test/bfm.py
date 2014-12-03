import subprocess

from migen.fhdl.std import *

from lib.sata.std import *
from lib.sata.link.test.common import *

class BFMDword():
	def __init__(self, dat=0):
		self.dat = dat
		self.start = 1
		self.done = 0

class BFMSource(Module):
	def __init__(self, dw):
		self.source = Source(phy_layout(dw))
		###
		self.dword = BFMDword()

	def send(self, dword):
		self.dword = dword

	def do_simulation(self, selfp):
		selfp.source.stb = 1
		selfp.source.charisk = 0b0000
		for k, v in primitives.items():
			if v == self.dword.dat:
				selfp.source.charisk = 0b0001
		selfp.source.data = self.dword.dat

class BFMSink(Module):
	def __init__(self, dw):
		self.sink = Sink(phy_layout(dw))
		###
		self.dword = BFMDword()

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

class BFMPHY(Module):
	def __init__(self, dw):
		self.dw = dw

		self.submodules.bfm_sink = BFMSink(dw)
		self.submodules.bfm_source = BFMSource(dw)

		self.source = self.bfm_source.source
		self.sink = self.bfm_sink.sink

		self.dword = 0

	def send(self, dword):
		packet = BFMDword(dword)
		self.bfm_source.send(packet)

	def receive(self):
		yield from self.bfm_sink.receive()
		self.rx_dword = self.bfm_sink.dword.dat

	def __repr__(self):
		# receive
		receiving = "%08x " %self.rx_dword
		receiving += decode_primitive(self.rx_dword)
		receiving += " "*(16-len(receiving))

		# send
		sending = "%08x " %self.bfm_source.dword.dat
		sending += decode_primitive(self.bfm_source.dword.dat)
		sending += " "*(16-len(sending))

		return receiving + sending


class BFM(Module):
	def __init__(self, dw, debug=False, hold_random_level=0):
		self.debug = debug
		self.hold_random_level = hold_random_level

		###

		self.submodules.phy = BFMPHY(dw)
		self.get_scrambler_ref()

		self.rx_cont_ongoing = False
		self.rx_packet_ongoing = False
		self.rx_packet = []

		self.run = True

	def get_scrambler_ref(self):
		with subprocess.Popen(["./scrambler"], stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
			process.stdin.write("0x10000".encode("ASCII"))
			out, err = process.communicate()
		self.scrambler_ref = [int(e, 16) for e in out.decode("utf-8").split("\n")[:-1]]

	def descramble(self, packet):
		p = []
		for i in range(len(packet)):
			v = packet[i] ^ self.scrambler_ref[i]
			p.append(v)
		return p

	def check_crc(self, packet):
		stdin = ""
		for v in packet[:-1]:
			stdin += "0x%08x " %v
		stdin += "exit"
		with subprocess.Popen("./crc", stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
			process.stdin.write(stdin.encode("ASCII"))
			out, err = process.communicate()
		crc = int(out.decode("ASCII"), 16)
		if packet[-1] != crc:
			return []
		else:
			return packet[:-1]

	def packet_callback(self, packet):
		packet = self.descramble(packet)
		packet = self.check_crc(packet)
		print("----")
		for v in packet:
			print("%08x" %v)
		print("----")

	def dword_callback(self, dword):
		if dword == primitives["CONT"]:
			self.rx_cont_ongoing = True
		elif is_primitive(dword):
			self.rx_cont_ongoing = False

		# X_RDY / WTRM response
		if dword == primitives["X_RDY"]:
			self.phy.send(primitives["R_RDY"])

		elif dword == primitives["WTRM"]:
			self.phy.send(primitives["R_OK"])

		# HOLD response
		elif dword == primitives["HOLD"]:
			self.phy.send(primitives["HOLDA"])

		# packet capture
		elif dword == primitives["EOF"]:
			self.rx_packet_ongoing = False
			self.packet_callback(self.rx_packet)

		elif self.rx_packet_ongoing:
			if dword != primitives["HOLD"]:
				n = randn(100)
				if n < self.hold_random_level:
					self.phy.send(primitives["HOLD"])
				else:
					self.phy.send(primitives["R_RDY"])
				if not is_primitive(dword):
					if not self.rx_cont_ongoing:
						self.rx_packet.append(dword)

		elif dword == primitives["SOF"]:
			self.rx_packet_ongoing = True
			self.rx_packet = []

	def gen_simulation(self, selfp):
		self.phy.send(primitives["SYNC"])
		while True:
			yield from self.phy.receive()
			if self.debug:
				print(self.phy)
			self.dword_callback(self.phy.rx_dword)
