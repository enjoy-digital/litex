from migen.bus import wishbone
from migen.fhdl.structure import *
from migen.corelogic.fsm import FSM
from migen.corelogic.misc import split, displacer, chooser
from migen.corelogic.record import Record

def _log2_int(n):
	l = 1
	r = 0
	while l < n:
		l *= 2
		r += 1
	if l == n:
		return r
	else:
		raise ValueError("Not a power of 2")

# cachesize (in 32-bit words) is the size of the data store, must be a power of 2
class WB2ASMI:
	def __init__(self, cachesize, asmiport):
		self.wishbone = wishbone.Slave()
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
		offsetbits = _log2_int(adw//32)
		addressbits = aaw + offsetbits
		linebits = _log2_int(self.cachesize) - offsetbits
		tagbits = aaw - linebits
		adr_offset, adr_line, adr_tag = split(self.wishbone.adr_i, offsetbits, linebits, tagbits)
		
		# Data memory
		data_adr = Signal(BV(linebits))
		data_do = Signal(BV(adw))
		data_di = Signal(BV(adw))
		data_we = Signal(BV(adw//8))
		data_port = MemoryPort(data_adr, data_do, data_we, data_di, we_granularity=8)
		data_mem = Memory(adw, 2**linebits, data_port)
		
		write_from_asmi = Signal()
		write_to_asmi = Signal()
		adr_offset_r = Signal(BV(offsetbits))
		comb += [
			data_adr.eq(adr_line),
			If(write_from_asmi,
				data_di.eq(self.asmiport.dat_r),
				data_we.eq(Replicate(1, adw//8))
			).Else(
				data_di.eq(Replicate(self.wishbone.dat_i, adw//32)),
				If(self.wishbone.cyc_i & self.wishbone.stb_i & self.wishbone.we_i & self.wishbone.ack_o,
					displacer(self.wishbone.sel_i, adr_offset, data_we, 2**offsetbits, reverse=True)
				)
			),
			If(write_to_asmi,
				self.asmiport.dat_w.eq(data_do),
				self.asmiport.dat_wm.eq(Replicate(1, adw//8))
			),
			chooser(data_do, adr_offset_r, self.wishbone.dat_o, reverse=True)
		]
		sync += [
			adr_offset_r.eq(adr_offset)
		]
		
		# Tag memory
		tag_layout = [("tag", BV(linebits)), ("dirty", BV(1))]
		tag_do = Record(tag_layout)
		tag_do_raw = tag_do.to_signal(comb, False)
		tag_di = Record(tag_layout)
		tag_di_raw = tag_di.to_signal(comb, True)
		
		tag_adr = Signal(BV(linebits))
		tag_we = Signal()
		tag_port = MemoryPort(tag_adr, tag_do_raw, tag_we, tag_di_raw)
		tag_mem = Memory(tagbits+1, 2**linebits, tag_port)
		
		comb += [
			tag_adr.eq(adr_line),
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
			If(self.wishbone.cyc_i & self.wishbone.stb_i, fsm.next_state(fsm.TEST_HIT))
		)
		fsm.act(fsm.TEST_HIT,
			If(tag_do.tag == adr_tag,
				self.wishbone.ack_o.eq(1),
				If(self.wishbone.we_i,
					tag_di.dirty.eq(1),
					tag_we.eq(1)
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
			tag_we.eq(1),
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
		
		return Fragment(comb, sync, memories=[data_mem, tag_mem]) \
			+ fsm.get_fragment()
