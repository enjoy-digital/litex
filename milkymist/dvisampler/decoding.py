from migen.fhdl.structure import *
from migen.fhdl.module import Module

class _TMDSDecoding(Module):
	def __init__(self):
		self.input = Signal(10)
		self.de = Signal()
		self.data = Signal(8)
		self.c = Signal(2)

		###

		self.sync.pix += self.de.eq(1)
		for i, t in enumerate([0b1101010100, 0b0010101011, 0b0101010100, 0b1010101011]):
			self.sync.pix += If(self.input == t,
				self.de.eq(0),
				self.c.eq(i)
			)
		self.sync.pix += self.data[0].eq(self.input[0] ^ self.input[9])
		for i in range(1, 8):
			self.sync.pix += self.data[i].eq(self.input[i] ^ self.input[i-1] ^ ~self.input[8])

class Decoding(Module):
	def __init__(self):
		self.valid_i = Signal()
		self.data0 = Signal(10)
		self.data1 = Signal(10)
		self.data2 = Signal(10)

		self.valid_o = Signal()
		self.de = Signal()
		self.r = Signal(8)
		self.g = Signal(8)
		self.b = Signal(8)
		self.hsync = Signal()
		self.vsync = Signal()

		###

		self.submodules.decode0 = _TMDSDecoding()
		self.submodules.decode1 = _TMDSDecoding()
		self.submodules.decode2 = _TMDSDecoding()

		self.comb += [
			self.decode0.input.eq(self.data0),
			self.decode1.input.eq(self.data1),
			self.decode2.input.eq(self.data2),

			self.de.eq(self.decode0.de),
			self.r.eq(self.decode2.data),
			self.g.eq(self.decode1.data),
			self.b.eq(self.decode0.data),
			self.hsync.eq(self.decode0.c[0]),
			self.vsync.eq(self.decode0.c[1])
		]

		self.sync.pix += self.valid_o.eq(self.valid_i)
