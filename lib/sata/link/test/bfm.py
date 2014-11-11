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
		elif selfp.source.stb == 1 and selfp.source.ack == 1:
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

	def gen_simulation(self, selfp):
		while True:
			yield from self.phy.receive()
			print("%08x" %(self.phy.rx_dword))
