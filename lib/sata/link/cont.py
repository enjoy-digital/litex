from lib.sata.common import *
from lib.sata.link.scrambler import Scrambler

from migen.genlib.misc import optree

class SATACONTInserter(Module):
	def __init__(self, description):
		self.sink = sink = Sink(description)
		self.source = source = Source(description)

		###

		self.counter = counter = Counter(max=4)

		is_data = Signal()
		was_data = Signal()
		was_hold = Signal()
		change = Signal()
		self.comb += is_data.eq(sink.charisk == 0)

		last_data = Signal(32)
		last_primitive = Signal(32)
		last_charisk = Signal(4)
		self.sync += [
			If(sink.stb & source.ack,
				last_data.eq(sink.data),
				last_charisk.eq(sink.charisk),
				If(~is_data,
					last_primitive.eq(sink.data),
				),
				was_data.eq(is_data),
				was_hold.eq(last_primitive == primitives["HOLD"])
			)
		]
		self.comb += change.eq(
			(sink.data != last_data) |
			(sink.charisk != last_charisk) |
			is_data
		)

		# scrambler
		self.scrambler = scrambler = InsertReset(Scrambler())

		# Datapath
		self.comb += [
			Record.connect(sink, source),
			If(sink.stb,
				If(~change,
					counter.ce.eq(sink.ack & (counter.value !=2)),
					# insert CONT
					If(counter.value == 1,
						source.charisk.eq(0b0001),
						source.data.eq(primitives["CONT"])
					# insert scrambled data for EMI
					).Elif(counter.value == 2,
						scrambler.ce.eq(sink.ack),
						source.charisk.eq(0b0000),
						source.data.eq(scrambler.value)
					)
				).Else(
					counter.reset.eq(source.ack),
					If(counter.value == 2,
						# Reinsert last primitive
						If(is_data | (~is_data & was_hold),
							source.stb.eq(1),
							sink.ack.eq(0),
							source.charisk.eq(0b0001),
							source.data.eq(last_primitive)
						)
					)
				)
			)
		]

class SATACONTRemover(Module):
	def __init__(self, description):
		self.sink = sink = Sink(description)
		self.source = source = Source(description)

		###

		is_data = Signal()
		is_cont = Signal()
		in_cont = Signal()
		cont_ongoing = Signal()

		self.comb += [
			is_data.eq(sink.charisk == 0),
			is_cont.eq(~is_data & (sink.data == primitives["CONT"]))
		]
		self.sync += \
			If(sink.stb & sink.ack,
				If(is_cont,
					in_cont.eq(1)
				).Elif(~is_data,
					in_cont.eq(0)
				)
			)
		self.comb += cont_ongoing.eq(is_cont | (in_cont & is_data))

		# Datapath
		last_primitive = Signal(32)
		self.sync += [
			If(sink.stb & sink.ack,
				If(~is_data & ~is_cont,
					last_primitive.eq(sink.data)
				)
			)
		]
		self.comb += [
			Record.connect(sink, source),
			If(cont_ongoing,
				source.charisk.eq(0b0001),
				source.data.eq(last_primitive)
			)
		]
