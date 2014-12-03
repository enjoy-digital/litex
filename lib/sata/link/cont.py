from migen.fhdl.std import *
from migen.genlib.misc import optree

from lib.sata.std import *
from lib.sata.link.scrambler import Scrambler

class SATACONTInserter(Module):
	def __init__(self, layout):
		self.sink = sink = Sink(layout)
		self.source = source = Source(layout)

		###

		# Detect consecutive primitives
		cnt = Signal(2)
		is_primitive = Signal()
		last_was_primitive = Signal()
		last_primitive = Signal(32)
		change = Signal()

		cont_insert = Signal()
		scrambler_insert = Signal()
		last_primitive_insert = Signal()

		self.comb += [
			is_primitive.eq(sink.charisk != 0),
			change.eq((sink.data != last_primitive) | ~is_primitive),
			cont_insert.eq(~change & (cnt==1)),
			scrambler_insert.eq(~change & (cnt==2)),
			last_primitive_insert.eq(~is_primitive & last_was_primitive & (cnt==2))
		]
		self.sync += \
			If(sink.stb & source.ack,
				If(is_primitive,
					last_primitive.eq(sink.data),
					last_was_primitive.eq(1)
				).Else(
					last_was_primitive.eq(0)
				),
				If(change,
					cnt.eq(0)
				).Else(
					If(~scrambler_insert,
						cnt.eq(cnt+1)
					)
				)
			)

		# Repeated primitives scranbler
		scrambler = Scrambler()
		self.submodules += scrambler
		self.comb += [
			scrambler.reset.eq(ResetSignal()), #XXX: should be on COMINIT / COMRESET
			scrambler.ce.eq(scrambler_insert & self.source.stb & self.source.ack)
		]

		# Datapath
		self.comb += [
			Record.connect(sink, source),
			If(self.sink.stb,
				If(cont_insert,
					source.charisk.eq(0b0001),
					source.data.eq(primitives["CONT"])
				).Elif(scrambler_insert,
					source.charisk.eq(0b0000),
					source.data.eq(scrambler.value)
				).Elif(last_primitive_insert,
					source.stb.eq(1),
					sink.ack.eq(0),
					source.charisk.eq(0b0001),
					source.data.eq(last_primitive)
				)
			)
		]
