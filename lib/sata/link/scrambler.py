from migen.fhdl.std import *
from migen.genlib.misc import optree

from lib.sata.std import *

@DecorateModule(InsertReset)
@DecorateModule(InsertCE)
class Scrambler(Module):
	"""SATA Scrambler

	Implement a SATA Scrambler

	Attributes
	----------
	value : out
		Scrambled value.
	"""
	def __init__(self):
		self.value = Signal(32)

		###

		context = Signal(16, reset=0xf0f6)
		next_value = Signal(32)
		self.sync += context.eq(next_value[16:32])

		# XXX: from SATA specification, replace it with
		# a generic implementation using polynoms.
		lfsr_coefs = (
			(15, 13, 4, 0), #0
			(15, 14, 13, 5, 4, 1, 0),
			(14, 13, 6, 5, 4, 2,1, 0),
			(15, 14, 7, 6, 5, 3,2, 1),
			(13, 8, 7, 6, 3, 2, 0),
			(14, 9, 8, 7, 4, 3, 1),
			(15, 10, 9, 8, 5, 4, 2),
			(15, 13, 11, 10, 9, 6, 5, 4, 3, 0),
			(15, 14, 13, 12, 11, 10,7, 6, 5, 1, 0),
			(14, 12, 11, 8, 7, 6, 4, 2, 1, 0),
			(15, 13, 12, 9, 8, 7, 5, 3, 2, 1),
			(15, 14, 10, 9, 8, 6, 3, 2, 0),
			(13, 11, 10, 9, 7, 3, 1, 0),
			(14, 12, 11, 10, 8, 4, 2, 1),
			(15, 13, 12, 11, 9, 5, 3, 2),
			(15, 14, 12, 10, 6, 3, 0),

			(11, 7, 1, 0), #16
			(12, 8, 2, 1),
			(13, 9, 3, 2),
			(14, 10, 4, 3),
			(15, 11, 5, 4),
			(15, 13, 12, 6, 5, 4, 0),
			(15, 14, 7, 6, 5, 4, 1, 0),
			(13, 8, 7, 6, 5, 4, 2, 1, 0),
			(14, 9, 8,7, 6, 5, 3, 2, 1),
			(15, 10, 9, 8, 7, 6, 4, 3, 2),
			(15, 13, 11, 10, 9, 8, 7, 5, 3, 0),
			(15, 14, 13, 12, 11, 10, 9, 8, 6, 1, 0),
			(14, 12, 11, 10, 9, 7, 4, 2, 1, 0),
			(15, 13, 12, 11, 10, 8, 5, 3, 2, 1),
			(15, 14, 12, 11, 9, 6, 3, 2, 0),
			(12, 10, 7, 3, 1, 0),
		)

		for n, coefs in enumerate(lfsr_coefs):
			eq = [context[i] for i in coefs]
			self.comb += next_value[n].eq(optree("^", eq))

		self.comb += self.value.eq(next_value)

class SATAScrambler(Module):
	def __init__(self, layout):
		self.sink = sink = Sink(layout)
		self.source = source = Source(layout)

		###

		self.submodules.scrambler = Scrambler()
		ongoing = Signal()
		self.sync += \
			If(sink.stb & sink.ack,
				If(sink.eop,
					ongoing.eq(0)
				).Elif(sink.sop,
					ongoing.eq(1)
				)
			)
		self.comb += [
			self.scrambler.ce.eq(sink.stb & sink.ack & (sink.sop | ongoing)),
			self.scrambler.reset.eq(~(sink.sop | ongoing)),
			Record.connect(sink, source),
			source.d.eq(sink.d ^ self.scrambler.value)
		]
