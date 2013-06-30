from migen.fhdl.std import *

"""
Encoders and decoders between binary and one-hot representation

i: input (binary or one-hot)
o: output (one-hot or binary)
n: "none" signal (in/out), binary value is invalid
"""

class Encoder(Module):
	def __init__(self, width):
		self.i = Signal(width) # one-hot
		self.o = Signal(max=width) # binary
		self.n = Signal() # invalid: none or multiple
		act = dict((1<<j, self.o.eq(j)) for j in range(width))
		act["default"] = self.n.eq(1)
		self.comb += Case(self.i, act)

class PriorityEncoder(Module):
	def __init__(self, width):
		self.i = Signal(width) # one-hot, lsb has priority
		self.o = Signal(max=width) # binary
		self.n = Signal() # none
		for j in range(width)[::-1]: # last has priority
			self.comb += If(self.i[j], self.o.eq(j))
		self.comb += self.n.eq(self.i == 0)

class Decoder(Module):
	def __init__(self, width):
		self.i = Signal(max=width) # binary
		self.n = Signal() # none/invalid
		self.o = Signal(width) # one-hot
		act = dict((j, self.o.eq(1<<j)) for j in range(width))
		self.comb += Case(self.i, act)
		self.comb += If(self.n, self.o.eq(0))

class PriorityDecoder(Decoder):
	pass # same

def _main():
	from migen.fhdl import verilog
	e = Encoder(8)
	print(verilog.convert(e, ios={e.i, e.o, e.n}))
	pe = PriorityEncoder(8)
	print(verilog.convert(pe, ios={pe.i, pe.o, pe.n}))
	d = Decoder(8)
	print(verilog.convert(d, ios={d.i, d.n, d.o}))

if __name__ == "__main__":
	_main()
