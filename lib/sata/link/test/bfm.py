import subprocess

from migen.fhdl.std import *

from lib.sata.std import *

class BFMDword():
	def __init__(self, dat=0):
		self.dat = dat
		self.start = 1
		self.done = 0

class BFMSource(Module):
	def __init__(self, dw):
		self.source = Source(phy_layout(dw))
		###
		self.dwords = []
		self.dword = BFMDword()
		self.dword.done = 1

	def send(self, dword, blocking=True):
		self.dwords.append(dword)
		if blocking:
			while dword.done == 0:
				yield

	def do_simulation(self, selfp):
		if len(self.dwords) and self.dword.done:
			self.dword = self.dwords.pop(0)
		if not self.dword.done:
			selfp.source.stb = 1
			selfp.source.charisk = 0b0000
			for k, v in primitives.items():
				if v == self.dword.dat:
					selfp.source.charisk = 0b0001
			selfp.source.data = self.dword.dat
		if selfp.source.stb == 1 and selfp.source.ack == 1:
				self.dword.done = 1
				selfp.source.stb = 0

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

	def send(self, dword, blocking=True):
		packet = BFMDword(dword)
		yield from self.bfm_source.send(dword, blocking)

	def receive(self):
		yield from self.bfm_sink.receive()
		self.rx_dword = self.bfm_sink.dword.dat

class BFM(Module):
	def __init__(self, dw, debug=False):
		self.debug = debug

		###

		self.submodules.phy = BFMPHY(dw)
		self.get_scrambler_ref()

		self.rx_packet_ongoing = False
		self.rx_packet = []

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
		# Todo from C Code or Python Code
		return packet[:-1]

	def packet_callback(self, packet):
		packet = self.descramble(packet)
		packet = self.check_crc(packet)
		for v in packet:
			print("%08x" %v)

	def dword_callback(self, dword):
		print("%08x " %dword, end="")
		for k, v in primitives.items():
			if dword == v:
				print(k, end="")
		print("")

		# X_RDY / WTRM response
		if dword == primitives["X_RDY"]:
			self.phy.bfm_source.dwords.append(BFMDword(primitives["R_RDY"]))
		if dword == primitives["WTRM"]:
			self.phy.bfm_source.dwords.append(BFMDword(primitives["R_OK"]))

		# packet capture
		if dword == primitives["EOF"]:
			self.rx_packet_ongoing = False
			self.packet_callback(self.rx_packet)

		if self.rx_packet_ongoing:
			self.rx_packet.append(dword)

		if dword == primitives["SOF"]:
			self.rx_packet_ongoing = True
			self.rx_packet = []

	def gen_simulation(self, selfp):
		self.phy.bfm_source.dwords.append(BFMDword(primitives["SYNC"]))
		while True:
			yield from self.phy.receive()
			self.dword_callback(self.phy.rx_dword)
