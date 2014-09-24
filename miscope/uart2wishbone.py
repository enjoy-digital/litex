from migen.fhdl.structure import *
from migen.fhdl.module import *
from migen.genlib.record import *
from migen.genlib.cdc import MultiReg
from migen.genlib.fsm import FSM, NextState
from migen.genlib.misc import split, displacer, chooser
from migen.bank.description import *
from migen.bus import wishbone
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
		rx_data = self.source.payload.d
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
				tx_reg.eq(self.sink.payload.d),
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

		# Tuning word value
		self._tuning_word = CSRStorage(32, reset=int((baud/clk_freq)*2**32))
		tuning_word = self._tuning_word.storage

		###

		self.submodules.rx = UARTRX(pads, tuning_word)
		self.submodules.tx = UARTTX(pads, tuning_word)

class Counter(Module):
	def __init__(self, width):
		self.value = Signal(width)
		self.clr = Signal()
		self.inc = Signal()
		self.sync += [
			If(self.clr,
				self.value.eq(0)
			).Elif(self.inc,
				self.value.eq(self.value+1)
			)
		]

class UARTPads:
	def __init__(self):
		self.rx = Signal()
		self.tx = Signal()

class UARTMux(Module):
	def __init__(self, pads):
		self.sel = Signal(max=2)
		self.shared_pads = UARTPads()
		self.bridge_pads = UARTPads()

	###
		# Route rx pad:
		# when sel==0, route it to shared rx and bridge rx
		# when sel==1, route it only to bridge rx
		self.comb += \
			If(self.sel==0,
				self.shared_pads.rx.eq(pads.rx),
				self.bridge_pads.rx.eq(pads.rx)
			).Else(
				self.bridge_pads.rx.eq(pads.rx)
			)

		# Route tx:
		# when sel==0, route shared tx to pads tx
		# when sel==1, route bridge tx to pads tx
		self.comb += \
			If(self.sel==0,
				pads.tx.eq(self.shared_pads.tx)
			).Else(
				pads.tx.eq(self.bridge_pads.tx)
			)

class UART2Wishbone(Module, AutoCSR):
	WRITE_CMD = 0x01
	READ_CMD = 0x02
	def __init__(self, pads, clk_freq, baud=115200, share_uart=False):

		# Wishbone interface
		self.wishbone = wishbone.Interface()
		if share_uart:
			self._sel = CSRStorage()

	###
		if share_uart:
			self.submodules.uart_mux = UARTMux(pads)
			self.submodules.uart = UART(self.uart_mux.bridge_pads, clk_freq, baud)
			self.shared_pads = self.uart_mux.shared_pads
			self.comb += self.uart_mux.sel.eq(self._sel.storage)
		else:
			self.submodules.uart = UART(pads, clk_freq, baud)

		uart = self.uart

		fsm = FSM()
		self.submodules += fsm

		word_cnt = Counter(3)
		burst_cnt = Counter(8)
		self.submodules += word_cnt, burst_cnt

		###
		cmd = Signal(8)
		fsm.act("WAIT_CMD",
			If(uart.rx.source.stb,
				If(	(uart.rx.source.payload.d == self.WRITE_CMD) |
					(uart.rx.source.payload.d == self.READ_CMD),
					NextState("RECEIVE_BURST_LENGTH")
				),
			word_cnt.clr.eq(1),
			burst_cnt.clr.eq(1)
			)
		)
		self.sync += If(fsm.ongoing("WAIT_CMD") & uart.rx.source.stb, cmd.eq(uart.rx.source.d))

		####
		burst_length = Signal(8)
		fsm.act("RECEIVE_BURST_LENGTH",
			word_cnt.inc.eq(uart.rx.source.stb),
			If(word_cnt.value == 1,
				word_cnt.clr.eq(1),
				NextState("RECEIVE_ADDRESS")
			)
		)
		self.sync += \
			If(fsm.ongoing("RECEIVE_BURST_LENGTH") & uart.rx.source.stb, burst_length.eq(uart.rx.source.d))

		####
		address = Signal(32)
		fsm.act("RECEIVE_ADDRESS",
			word_cnt.inc.eq(uart.rx.source.stb),
			If(word_cnt.value == 4,
				word_cnt.clr.eq(1),
				If(cmd == self.WRITE_CMD,
					NextState("RECEIVE_DATA")
				).Elif(cmd == self.READ_CMD,
					NextState("READ_DATA")
				)
			)
		)
		self.sync += \
			If(fsm.ongoing("RECEIVE_ADDRESS") & uart.rx.source.stb,
					address.eq(Cat(uart.rx.source.d, address[0:24]))
			)

		###
		data = Signal(32)

		###
		fsm.act("RECEIVE_DATA",
			word_cnt.inc.eq(uart.rx.source.stb),
			If(word_cnt.value == 4,
				word_cnt.clr.eq(1),
				NextState("WRITE_DATA")
			)
		)

		fsm.act("WRITE_DATA",
			self.wishbone.adr.eq(address + burst_cnt.value),
			self.wishbone.dat_w.eq(data),
			self.wishbone.sel.eq(2**flen(self.wishbone.sel)-1),
			self.wishbone.stb.eq(1),
			self.wishbone.we.eq(1),
			self.wishbone.cyc.eq(1),
			If(self.wishbone.ack,
				burst_cnt.inc.eq(1),
				If(burst_cnt.value == (burst_length-1),
					NextState("WAIT_CMD")
				).Else(
					word_cnt.clr.eq(1),
					NextState("RECEIVE_DATA")
				)
			)
		)

		###
		fsm.act("READ_DATA",
			self.wishbone.adr.eq(address + burst_cnt.value),
			self.wishbone.sel.eq(2**flen(self.wishbone.sel)-1),
			self.wishbone.stb.eq(1),
			self.wishbone.we.eq(0),
			self.wishbone.cyc.eq(1),
			If(self.wishbone.stb & self.wishbone.ack,
				word_cnt.clr.eq(1),
				NextState("SEND_DATA")
			)
		)

		fsm.act("SEND_DATA",
			word_cnt.inc.eq(uart.tx.sink.ack),
			If(word_cnt.value == 4,
				burst_cnt.inc.eq(1),
				If(burst_cnt.value == (burst_length-1),
					NextState("WAIT_CMD")
				).Else(
					NextState("READ_DATA")
				)
			),
			uart.tx.sink.stb.eq(1),
			chooser(data, word_cnt.value, uart.tx.sink.d, n=4, reverse=True)
		)

		###
		self.sync += \
			If(fsm.ongoing("RECEIVE_DATA") & uart.rx.source.stb,
				data.eq(Cat(uart.rx.source.d, data[0:24]))
			).Elif(fsm.ongoing("READ_DATA") & self.wishbone.stb & self.wishbone.ack,
				data.eq(self.wishbone.dat_r)
			)
