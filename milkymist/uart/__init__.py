from migen.fhdl.structure import *
from migen.bank.description import *
from migen.bank.eventmanager import *
from migen.bank import csrgen

class UART:
	def __init__(self, address, clk_freq, baud=115200):
		self._rxtx = RegisterRaw("rxtx", 8)
		self._divisor = RegisterField("divisor", 16, reset=int(clk_freq/baud/16))
		
		self._tx_event = EventSourceLevel()
		self.events = EventManager(self._tx_event)
		self.bank = csrgen.Bank([self._rxtx, self._divisor] + self.events.get_registers(),
			address=address)

		self.tx = Signal(reset=1)
		self.rx = Signal()
	
	def get_fragment(self):
		enable16 = Signal()
		enable16_counter = Signal(BV(16))
		comb = [
			enable16.eq(enable16_counter == Constant(0, BV(16)))
		]
		sync = [
			enable16_counter.eq(enable16_counter - 1),
			If(enable16,
				enable16_counter.eq(self._divisor.field.r - 1))
		]
		
		tx_reg = Signal(BV(8))
		tx_bitcount = Signal(BV(4))
		tx_count16 = Signal(BV(4))
		tx_busy = Signal()
		sync += [
			If(self._rxtx.re,
				tx_reg.eq(self._rxtx.r),
				tx_bitcount.eq(0),
				tx_count16.eq(1),
				tx_busy.eq(1),
				self.tx.eq(0)
			).Elif(enable16 & tx_busy,
				tx_count16.eq(tx_count16 + 1),
				If(tx_count16 == Constant(0, BV(4)),
					tx_bitcount.eq(tx_bitcount + 1),
					If(tx_bitcount == 8,
						self.tx.eq(1)
					).Elif(tx_bitcount == 9,
						self.tx.eq(1),
						tx_busy.eq(0)
					).Else(
						self.tx.eq(tx_reg[0]),
						tx_reg.eq(Cat(tx_reg[1:], 0))
					)
				)
			)
		]
		comb.append(self._tx_event.trigger.eq(tx_busy))
		
		return self.bank.get_fragment() \
			+ self.events.get_fragment() \
			+ Fragment(comb, sync, pads={self.tx, self.rx})
