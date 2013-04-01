from migen.fhdl.structure import *
from migen.fhdl.specials import Memory
from migen.bus import wishbone
from migen.genlib.fsm import FSM
from migen.genlib.misc import split, displacer, chooser
from migen.genlib.record import Record, layout_len

# cachesize (in 32-bit words) is the size of the data store, must be a power of 2
class WB2ASMI:
	def __init__(self, cachesize, asmiport):
		self.wishbone = wishbone.Interface()
		self.cachesize = cachesize
		self.asmiport = asmiport
		if len(self.asmiport.slots) != 1:
			raise ValueError("ASMI port must have 1 slot")
		if self.asmiport.hub.dw <= 32:
			raise ValueError("ASMI data width must be strictly larger than 32")
		if (self.asmiport.hub.dw % 32) != 0:
			raise ValueError("ASMI data width must be a multiple of 32")

	def get_fragment(self):
		comb = []
		sync = []
		
		aaw = self.asmiport.hub.aw
		adw = self.asmiport.hub.dw
		
		# Split address:
		# TAG | LINE NUMBER | LINE OFFSET
		offsetbits = log2_int(adw//32)
		addressbits = aaw + offsetbits
		linebits = log2_int(self.cachesize) - offsetbits
		tagbits = addressbits - linebits
		adr_offset, adr_line, adr_tag = split(self.wishbone.adr, offsetbits, linebits, tagbits)
		
		# Data memory
		data_mem = Memory(adw, 2**linebits)
		data_port = data_mem.get_port(write_capable=True, we_granularity=8)
		
		write_from_asmi = Signal()
		write_to_asmi = Signal()
		adr_offset_r = Signal(offsetbits)
		comb += [
			data_port.adr.eq(adr_line),
			If(write_from_asmi,
				data_port.dat_w.eq(self.asmiport.dat_r),
				data_port.we.eq(Replicate(1, adw//8))
			).Else(
				data_port.dat_w.eq(Replicate(self.wishbone.dat_w, adw//32)),
				If(self.wishbone.cyc & self.wishbone.stb & self.wishbone.we & self.wishbone.ack,
					displacer(self.wishbone.sel, adr_offset, data_port.we, 2**offsetbits, reverse=True)
				)
			),
			If(write_to_asmi, self.asmiport.dat_w.eq(data_port.dat_r)),
			self.asmiport.dat_wm.eq(0),
			chooser(data_port.dat_r, adr_offset_r, self.wishbone.dat_r, reverse=True)
		]
		sync += [
			adr_offset_r.eq(adr_offset)
		]
		
		# Tag memory
		tag_layout = [("tag", tagbits), ("dirty", 1)]
		tag_mem = Memory(layout_len(tag_layout), 2**linebits)
		tag_port = tag_mem.get_port(write_capable=True)
		tag_do = Record(tag_layout)
		tag_di = Record(tag_layout)
		comb += [
			tag_do.raw_bits().eq(tag_port.dat_r),
			tag_port.dat_w.eq(tag_di.raw_bits())
		]
			
		comb += [
			tag_port.adr.eq(adr_line),
			tag_di.tag.eq(adr_tag),
			self.asmiport.adr.eq(Cat(adr_line, tag_do.tag))
		]
		
		# Control FSM
		write_to_asmi_pre = Signal()
		sync.append(write_to_asmi.eq(write_to_asmi_pre))
		
		fsm = FSM("IDLE", "TEST_HIT",
			"EVICT_ISSUE", "EVICT_WAIT",
			"REFILL_WRTAG", "REFILL_ISSUE", "REFILL_WAIT", "REFILL_COMPLETE")
		
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
					fsm.next_state(fsm.EVICT_ISSUE)
				).Else(
					fsm.next_state(fsm.REFILL_WRTAG)
				)
			)
		)
		
		fsm.act(fsm.EVICT_ISSUE,
			self.asmiport.stb.eq(1),
			self.asmiport.we.eq(1),
			If(self.asmiport.ack, fsm.next_state(fsm.EVICT_WAIT))
		)
		fsm.act(fsm.EVICT_WAIT,
			# Data is actually sampled by the memory controller in the next state.
			# But since the data memory has one cycle latency, it gets the data
			# at the address given during this cycle.
			If(self.asmiport.get_call_expression(),
				write_to_asmi_pre.eq(1),
				fsm.next_state(fsm.REFILL_WRTAG)
			)
		)
		
		fsm.act(fsm.REFILL_WRTAG,
			# Write the tag first to set the ASMI address
			tag_port.we.eq(1),
			fsm.next_state(fsm.REFILL_ISSUE)
		)
		fsm.act(fsm.REFILL_ISSUE,
			self.asmiport.stb.eq(1),
			If(self.asmiport.ack, fsm.next_state(fsm.REFILL_WAIT))
		)
		fsm.act(fsm.REFILL_WAIT,
			If(self.asmiport.get_call_expression(), fsm.next_state(fsm.REFILL_COMPLETE))
		)
		fsm.act(fsm.REFILL_COMPLETE,
			write_from_asmi.eq(1),
			fsm.next_state(fsm.TEST_HIT)
		)
		
		return Fragment(comb, sync, specials={data_mem, tag_mem}) \
			+ fsm.get_fragment()
