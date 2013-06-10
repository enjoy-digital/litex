from migen.fhdl.std import *
from migen.bus import wishbone
from migen.genlib.fsm import FSM
from migen.genlib.misc import split, displacer, chooser
from migen.genlib.record import Record, layout_len

# cachesize (in 32-bit words) is the size of the data store, must be a power of 2
class WB2LASMI(Module):
	def __init__(self, cachesize, lasmim):
		self.wishbone = wishbone.Interface()

		###

		if lasmim.dw <= 32:
			raise ValueError("LASMI data width must be strictly larger than 32")
		if (lasmim.dw % 32) != 0:
			raise ValueError("LASMI data width must be a multiple of 32")

		# Split address:
		# TAG | LINE NUMBER | LINE OFFSET
		offsetbits = log2_int(lasmim.dw//32)
		addressbits = lasmim.aw + offsetbits
		linebits = log2_int(cachesize) - offsetbits
		tagbits = addressbits - linebits
		adr_offset, adr_line, adr_tag = split(self.wishbone.adr, offsetbits, linebits, tagbits)
		
		# Data memory
		data_mem = Memory(lasmim.dw, 2**linebits)
		data_port = data_mem.get_port(write_capable=True, we_granularity=8)
		self.specials += data_mem, data_port
		
		write_from_lasmi = Signal()
		write_to_lasmi = Signal()
		adr_offset_r = Signal(offsetbits)
		self.comb += [
			data_port.adr.eq(adr_line),
			If(write_from_lasmi,
				data_port.dat_w.eq(lasmim.dat_r),
				data_port.we.eq(Replicate(1, lasmim.dw//8))
			).Else(
				data_port.dat_w.eq(Replicate(self.wishbone.dat_w, lasmim.dw//32)),
				If(self.wishbone.cyc & self.wishbone.stb & self.wishbone.we & self.wishbone.ack,
					displacer(self.wishbone.sel, adr_offset, data_port.we, 2**offsetbits, reverse=True)
				)
			),
			If(write_to_lasmi, 
				lasmim.dat_w.eq(data_port.dat_r),
				lasmim.dat_we.eq(2**(lasmim.dw//8)-1)
			),
			chooser(data_port.dat_r, adr_offset_r, self.wishbone.dat_r, reverse=True)
		]
		self.sync += adr_offset_r.eq(adr_offset)
		
		# Tag memory
		tag_layout = [("tag", tagbits), ("dirty", 1)]
		tag_mem = Memory(layout_len(tag_layout), 2**linebits)
		tag_port = tag_mem.get_port(write_capable=True)
		self.specials += tag_mem, tag_port
		tag_do = Record(tag_layout)
		tag_di = Record(tag_layout)
		self.comb += [
			tag_do.raw_bits().eq(tag_port.dat_r),
			tag_port.dat_w.eq(tag_di.raw_bits())
		]
			
		self.comb += [
			tag_port.adr.eq(adr_line),
			tag_di.tag.eq(adr_tag),
			lasmim.adr.eq(Cat(adr_line, tag_do.tag))
		]
		
		# Control FSM
		assert(lasmim.write_latency >= 1 and lasmim.read_latency >= 1)
		fsm = FSM("IDLE", "TEST_HIT",
			"EVICT_REQUEST", "EVICT_DATA",
			"REFILL_WRTAG", "REFILL_REQUEST", "REFILL_DATA",
			delayed_enters=[
				("EVICT_DATAD", "EVICT_DATA", lasmim.write_latency-1),
				("REFILL_DATAD", "REFILL_DATA", lasmim.read_latency-1)
			])
		self.submodules += fsm
		
		fsm.act(fsm.IDLE,
			If(self.wishbone.cyc & self.wishbone.stb, fsm.next_state(fsm.TEST_HIT))
		)
		fsm.act(fsm.TEST_HIT,
			If(tag_do.tag == adr_tag,
				self.wishbone.ack.eq(1),
				If(self.wishbone.we,
					tag_di.dirty.eq(1),
					tag_port.we.eq(1)
				),
				fsm.next_state(fsm.IDLE)
			).Else(
				If(tag_do.dirty,
					fsm.next_state(fsm.EVICT_REQUEST)
				).Else(
					fsm.next_state(fsm.REFILL_WRTAG)
				)
			)
		)
		
		fsm.act(fsm.EVICT_REQUEST,
			lasmim.stb.eq(1),
			lasmim.we.eq(1),
			If(lasmim.ack, fsm.next_state(fsm.EVICT_DATAD))
		)
		fsm.act(fsm.EVICT_DATA,
			write_to_lasmi.eq(1),
			fsm.next_state(fsm.REFILL_WRTAG)
		)
		
		fsm.act(fsm.REFILL_WRTAG,
			# Write the tag first to set the LASMI address
			tag_port.we.eq(1),
			fsm.next_state(fsm.REFILL_REQUEST)
		)
		fsm.act(fsm.REFILL_REQUEST,
			lasmim.stb.eq(1),
			If(lasmim.ack, fsm.next_state(fsm.REFILL_DATAD))
		)
		fsm.act(fsm.REFILL_DATA,
			write_from_lasmi.eq(1),
			fsm.next_state(fsm.TEST_HIT)
		)
