from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.genlib.fsm import FSM
from migen.bank.description import *
from migen.bank.eventmanager import *
from migen.flow.actor import *
from migen.actorlib import dma_asmi

from milkymist.dvisampler.common import frame_layout

# Slot status: EMPTY=0 LOADED=1 PENDING=2
class _Slot(Module, AutoCSR):
	def __init__(self, addr_bits, alignment_bits):
		self.ev_source = EventSourceLevel()
		self.address = Signal(addr_bits)
		self.address_valid = Signal()
		self.address_done = Signal()

		self._r_status = CSRStorage(2, write_from_dev=True)
		self._r_address = CSRStorage(addr_bits + alignment_bits, alignment_bits=alignment_bits)

		###

		self.comb += [
			self.address.eq(self._r_address.storage),
			self.address_valid.eq(self._r_status.storage[0]),
			self._r_status.dat_w.eq(2),
			self._r_status.we.eq(self.address_done),
			self.ev_source.trigger.eq(self._r_status.storage[1])
		]

class _SlotArray(Module, AutoCSR):
	def __init__(self, nslots, addr_bits, alignment_bits):
		self.submodules.ev = EventManager()
		self.address = Signal(addr_bits)
		self.address_valid = Signal()
		self.address_done = Signal()

		###

		slots = [_Slot(addr_bits, alignment_bits) for i in range(nslots)]
		for n, slot in enumerate(slots):
			setattr(self.submodules, "slot"+str(n), slot)
			setattr(self.ev, "slot"+str(n), slot.ev_source)
		self.ev.finalize()

		change_slot = Signal()
		current_slot = Signal(max=nslots)
		self.sync += If(change_slot, [If(slot.address_valid, current_slot.eq(n)) for n, slot in reversed(list(enumerate(slots)))])
		self.comb += change_slot.eq(~self.address_valid | self.address_done)

		self.comb += [
			self.address.eq(Array(slot.address for slot in slots)[current_slot]),
			self.address_valid.eq(Array(slot.address_valid for slot in slots)[current_slot])
		]
		self.comb += [slot.address_done.eq(self.address_done & (current_slot == n)) for n, slot in enumerate(slots)]

class DMA(Module):
	def __init__(self, asmiport, nslots):
		bus_aw = asmiport.hub.aw
		bus_dw = asmiport.hub.dw
		alignment_bits = bits_for(bus_dw//8) - 1

		self.frame = Sink(frame_layout)
		self._r_frame_size = CSRStorage(bus_aw + alignment_bits, alignment_bits=alignment_bits)
		self.submodules._slot_array = _SlotArray(nslots, bus_aw, alignment_bits)
		self.ev = self._slot_array.ev

		###

		# start of frame detection
		sof = Signal()
		parity_r = Signal()
		self.sync += If(self.frame.stb & self.frame.ack, parity_r.eq(self.frame.payload.parity))
		self.comb += sof.eq(parity_r ^ self.frame.payload.parity)

		# address generator + maximum memory word count to prevent DMA buffer overrun
		reset_words = Signal()
		count_word = Signal()
		last_word = Signal()
		current_address = Signal(bus_aw)
		mwords_remaining = Signal(bus_aw)
		self.comb += last_word.eq(mwords_remaining == 1)
		self.sync += [
			If(reset_words,
				current_address.eq(self._slot_array.address),
				mwords_remaining.eq(self._r_frame_size.storage)
			).Elif(count_word,
				current_address.eq(current_address + 1),
				mwords_remaining.eq(mwords_remaining - 1)
			)
		]

		# pack pixels into memory words
		write_pixel = Signal()
		last_pixel = Signal()
		cur_memory_word = Signal(bus_dw)
		encoded_pixel = Signal(32)
		self.comb += [
			encoded_pixel.eq(Cat(
				self.frame.payload.b[6:], self.frame.payload.b,
				self.frame.payload.g[6:], self.frame.payload.g,
				self.frame.payload.r[6:], self.frame.payload.r))
		]
		pack_factor = bus_dw//32
		assert(pack_factor & (pack_factor - 1) == 0) # only support powers of 2
		pack_counter = Signal(max=pack_factor)
		self.comb += last_pixel.eq(pack_counter == (pack_factor - 1))
		self.sync += If(write_pixel,
				[If(pack_counter == (pack_factor-i-1),
					cur_memory_word[32*i:32*(i+1)].eq(encoded_pixel)) for i in range(pack_factor)],
				pack_counter.eq(pack_counter + 1)
			)

		# bus accessor
		self.submodules._bus_accessor = dma_asmi.Writer(asmiport)
		self.comb += [
			self._bus_accessor.address_data.payload.a.eq(current_address),
			self._bus_accessor.address_data.payload.d.eq(cur_memory_word)
		]

		# control FSM
		fsm = FSM("WAIT_SOF", "TRANSFER_PIXEL", "TO_MEMORY", "EOF")
		self.submodules += fsm

		fsm.act(fsm.WAIT_SOF,
			reset_words.eq(1),
			self.frame.ack.eq(~self._slot_array.address_valid | ~sof),
			If(self._slot_array.address_valid & sof & self.frame.stb, fsm.next_state(fsm.TRANSFER_PIXEL))
		)
		fsm.act(fsm.TRANSFER_PIXEL,
			self.frame.ack.eq(1),
			If(self.frame.stb,
				write_pixel.eq(1),
				If(last_pixel,
					fsm.next_state(fsm.TO_MEMORY)
				)
			)
		)
		fsm.act(fsm.TO_MEMORY,
			self._bus_accessor.address_data.stb.eq(1),
			If(self._bus_accessor.address_data.ack,
				count_word.eq(1),
				If(last_word,
					fsm.next_state(fsm.EOF)
				).Else(
					fsm.next_state(fsm.TRANSFER_PIXEL)
				)
			)
		)
		fsm.act(fsm.EOF,
			If(~self._bus_accessor.busy,
				self._slot_array.address_done.eq(1),
				fsm.next_state(fsm.WAIT_SOF)
			)
		)

	def get_csrs(self):
		return [self._r_frame_size] + self._slot_array.get_csrs()
