from migen.fhdl.std import *
from migen.genlib.cdc import MultiReg
from migen.bank.description import *
from migen.bank.eventmanager import *
from migen.genlib.record import Record
from migen.flow.actor import Sink, Source

class UARTRX(Module):
	def __init__(self, pads, tuning_word):
		self.source = Source([("d", 8)])

		###

		uart_clk_rxen = Signal()
		phase_accumulator_rx = Signal(32)

		rx = Signal()
		self.specials += MultiReg(pads.rx, rx)
		rx_r = Signal()
		rx_reg = Signal(8)
		rx_bitcount = Signal(4)
		rx_busy = Signal()
		rx_done = self.source.stb
		rx_data = self.source.d
		self.sync += [
			rx_done.eq(0),
			rx_r.eq(rx),
			If(~rx_busy,
				If(~rx & rx_r, # look for start bit
					rx_busy.eq(1),
					rx_bitcount.eq(0),
				)
			).Else(
				If(uart_clk_rxen,
					rx_bitcount.eq(rx_bitcount + 1),
					If(rx_bitcount == 0,
						If(rx, # verify start bit
							rx_busy.eq(0)
						)
					).Elif(rx_bitcount == 9,
						rx_busy.eq(0),
						If(rx, # verify stop bit
							rx_data.eq(rx_reg),
							rx_done.eq(1)
						)
					).Else(
						rx_reg.eq(Cat(rx_reg[1:], rx))
					)
				)
			)
		]
		self.sync += \
				If(rx_busy,
					Cat(phase_accumulator_rx, uart_clk_rxen).eq(phase_accumulator_rx + tuning_word)
				).Else(
					Cat(phase_accumulator_rx, uart_clk_rxen).eq(2**31)
				)

class UARTTX(Module):
	def __init__(self, pads, tuning_word):
		self.sink = Sink([("d", 8)])

		###

		uart_clk_txen = Signal()
		phase_accumulator_tx = Signal(32)

		pads.tx.reset = 1

		tx_reg = Signal(8)
		tx_bitcount = Signal(4)
		tx_busy = Signal()
		self.sync += [
			self.sink.ack.eq(0),
			If(self.sink.stb & ~tx_busy & ~self.sink.ack,
				tx_reg.eq(self.sink.d),
				tx_bitcount.eq(0),
				tx_busy.eq(1),
				pads.tx.eq(0)
			).Elif(uart_clk_txen & tx_busy,
				tx_bitcount.eq(tx_bitcount + 1),
				If(tx_bitcount == 8,
					pads.tx.eq(1)
				).Elif(tx_bitcount == 9,
					pads.tx.eq(1),
					tx_busy.eq(0),
					self.sink.ack.eq(1),
				).Else(
					pads.tx.eq(tx_reg[0]),
					tx_reg.eq(Cat(tx_reg[1:], 0))
				)
			)
		]
		self.sync += [
				If(tx_busy,
					Cat(phase_accumulator_tx, uart_clk_txen).eq(phase_accumulator_tx + tuning_word)
				).Else(
					Cat(phase_accumulator_tx, uart_clk_txen).eq(0)
				)
		]

class UART(Module, AutoCSR):
	def __init__(self, pads, clk_freq, baud=115200):
		self._r_rxtx = CSR(8)

		self.submodules.ev = EventManager()
		self.ev.tx = EventSourcePulse()
		self.ev.rx = EventSourcePulse()
		self.ev.finalize()

		# Tuning word value
		self._tuning_word = CSRStorage(32, reset=int((baud/clk_freq)*2**32))
		tuning_word = self._tuning_word.storage

		###

		self.submodules.rx = UARTRX(pads, tuning_word)
		self.submodules.tx = UARTTX(pads, tuning_word)

		self.sync += [
			If(self._r_rxtx.re,
				self.tx.sink.stb.eq(1),
				self.tx.sink.d.eq(self._r_rxtx.r),
			).Elif(self.tx.sink.ack,
				self.tx.sink.stb.eq(0)
			),
			If(self.rx.source.stb,
				self._r_rxtx.w.eq(self.rx.source.d)
			)
		]
		self.comb += [
			self.ev.tx.trigger.eq(self.tx.sink.stb & self.tx.sink.ack),
			self.ev.rx.trigger.eq(self.rx.source.stb) #self.rx.source.ack supposed to be always 1
		]

class UARTTB(Module):
	def __init__(self):
		self.clk_freq = 83333333
		self.baud = 3000000
		self.pads = Record([("rx", 1), ("tx", 1)])
		self.submodules.slave = UART(self.pads, self.clk_freq, self.baud)

	def wait_for(self, ns_time):
		freq_in_ghz = self.clk_freq/(10**9)
		period = 1/freq_in_ghz
		num_loops = int(ns_time/period)
		for i in range(num_loops+1):
			yield

	def gen_simulation(self, selfp):
		baud_in_ghz = self.baud/(10**9)
		uart_period = int(1/baud_in_ghz)
		half_uart_period = int(1/(2*baud_in_ghz))

		# Set TX an RX lines idle
		selfp.pads.tx = 1
		selfp.pads.rx = 1
		yield

		# First send a few characters

		tx_string = "01234"
		print("Sending string: " + tx_string)
		for c in tx_string:
			selfp.slave._r_rxtx.r = ord(c)
			selfp.slave._r_rxtx.re = 1
			yield
			selfp.slave._r_rxtx.re = 0

			yield from self.wait_for(half_uart_period)

			if selfp.pads.tx:
				print("FAILURE: no start bit sent")

			val = 0
			for i in range(8):
				yield from self.wait_for(uart_period)
				val >>= 1
				if selfp.pads.tx:
					val |= 0x80

			yield from self.wait_for(uart_period)

			if selfp.pads.tx == 0:
				print("FAILURE: no stop bit sent")

			if ord(c) != val:
				print("FAILURE: sent decimal value "+str(val)+" (char "+chr(val)+") instead of "+c)
			else:
				print("SUCCESS: sent "+c)
			while selfp.slave.ev.tx.trigger != 1:
				yield

		# Then receive a character

		rx_string = '5'
		print("Receiving character "+rx_string)
		rx_value = ord(rx_string)
		for i in range(11):
			if (i == 0):
				# start bit
				selfp.pads.rx = 0
			elif (i == 9):
				# stop bit
				selfp.pads.rx = 1
			elif (i == 10):
				selfp.pads.rx = 1
				break
			else:
				selfp.pads.rx = 1 if (rx_value & 1) else 0
				rx_value >>= 1
			yield from self.wait_for(uart_period)

		rx_value = ord(rx_string)
		received_value = selfp.slave._r_rxtx.w
		if (received_value == rx_value):
			print("RX SUCCESS: ")
		else:
			print("RX FAILURE: ")

		print("received "+chr(received_value))

		while True:
			yield

if __name__ == "__main__":
	from migen.sim.generic import Simulator, TopLevel
	from migen.sim import icarus
	with Simulator(UARTTB(), TopLevel("top.vcd", clk_period=int(1/0.08333333)), icarus.Runner(keep_files=False)) as s:
		s.run(20000)
