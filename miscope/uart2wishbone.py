from migen.fhdl.structure import *
from migen.fhdl.module import *
from migen.genlib.record import *
from migen.genlib.cdc import MultiReg
from migen.genlib.fsm import FSM, NextState
from migen.genlib.misc import split, displacer, chooser
from migen.bank.description import *
from migen.bus import wishbone


# Todo
# ----
# - implement timeout in fsm to prevent deadlocks

def rec_rx():
	layout = [
			("stb", 1, DIR_M_TO_S),
			("dat", 8, DIR_M_TO_S)
		]
	return Record(layout)

def rec_tx():
	layout = [
			("stb", 1, DIR_M_TO_S),
			("ack", 1, DIR_S_TO_M),
			("dat", 8, DIR_M_TO_S)
		]
	return Record(layout)

class UART(Module):
	def __init__(self, pads, clk_freq, baud=115200):

		self.rx = rec_rx()
		self.tx = rec_tx()

		self.divisor = Signal(16, reset=int(clk_freq/baud/16))

		pads.tx.reset = 1
	
		###

		enable16 = Signal()
		enable16_counter = Signal(16)
		self.comb += enable16.eq(enable16_counter == 0)
		self.sync += [
			enable16_counter.eq(enable16_counter - 1),
			If(enable16,
				enable16_counter.eq(self.divisor - 1))
		]
		
		# TX
		tx_reg = Signal(8)
		tx_bitcount = Signal(4)
		tx_count16 = Signal(4)
		tx_done = self.tx.ack
		tx_busy = Signal()
		tx_stb_d = Signal()
		self.sync += [
			tx_stb_d.eq(self.tx.stb & ~tx_done),
			tx_done.eq(0),
			If(self.tx.stb & ~tx_stb_d,
				tx_reg.eq(self.tx.dat),
				tx_bitcount.eq(0),
				tx_count16.eq(1),
				tx_busy.eq(1),
				pads.tx.eq(0)
			).Elif(enable16 & tx_busy,
				tx_count16.eq(tx_count16 + 1),
				If(tx_count16 == 0,
					tx_bitcount.eq(tx_bitcount + 1),
					If(tx_bitcount == 8,
						pads.tx.eq(1)
					).Elif(tx_bitcount == 9,
						pads.tx.eq(1),
						tx_busy.eq(0),
						tx_done.eq(1)
					).Else(
						pads.tx.eq(tx_reg[0]),
						tx_reg.eq(Cat(tx_reg[1:], 0))
					)
				)
			)
		]
		
		# RX
		rx = Signal()
		self.specials += MultiReg(pads.rx, rx, "sys")
		rx_r = Signal()
		rx_reg = Signal(8)
		rx_bitcount = Signal(4)
		rx_count16 = Signal(4)
		rx_busy = Signal()
		rx_done = self.rx.stb
		rx_data = self.rx.dat
		self.sync += [
			rx_done.eq(0),
			If(enable16,
				rx_r.eq(rx),
				If(~rx_busy,
					If(~rx & rx_r, # look for start bit
						rx_busy.eq(1),
						rx_count16.eq(7),
						rx_bitcount.eq(0)
					)
				).Else(
					rx_count16.eq(rx_count16 + 1),
					If(rx_count16 == 0,
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
			)
		]

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
	def __init__(self, pads, nb):
		self.sel = Signal(max=nb)
		self.pads = [UARTPads() for i in range(nb)]

	###	
		# Route Rx pad to all modules
		for i in range(nb):
			self.comb += self.pads[i].rx.eq(pads.rx)

		# Route only selected module to Tx pad
		pads_tx = [self.pads[i].tx for i in range(nb)]
		self.comb += chooser(Cat(pads_tx), self.sel, pads.tx, n=nb)


class UART2Wishbone(Module, AutoCSR):
	WRITE_CMD = 0x01
	READ_CMD = 0x02
	def __init__(self, pads, clk_freq, baud, share_uart=False):
		
		# Wishbone interface
		self.wishbone = wishbone.Interface()
		if share_uart:
			self._sel = CSRStorage()

	###
		if share_uart:
			self.submodules.uart_mux = UARTMux(pads, 2)
			self.submodules.uart = UART(self.uart_mux.pads[1], clk_freq, baud)
			self.shared_pads = self.uart_mux.pads[0]
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
			If(uart.rx.stb,
				If(	(uart.rx.dat == self.WRITE_CMD) |
					(uart.rx.dat == self.READ_CMD),
					NextState("RECEIVE_BURST_LENGTH")
				),
			word_cnt.clr.eq(1),
			burst_cnt.clr.eq(1)
			)
		)
		self.sync += If(fsm.ongoing("WAIT_CMD") & uart.rx.stb, cmd.eq(uart.rx.dat))

		####
		burst_length = Signal(8)
		fsm.act("RECEIVE_BURST_LENGTH",
			word_cnt.inc.eq(uart.rx.stb),
			If(word_cnt.value == 1, 
				word_cnt.clr.eq(1),
				NextState("RECEIVE_ADDRESS")
			)
		)
		self.sync += \
			If(fsm.ongoing("RECEIVE_BURST_LENGTH") & uart.rx.stb, burst_length.eq(uart.rx.dat)) 

		####
		address = Signal(32)
		fsm.act("RECEIVE_ADDRESS",
			word_cnt.inc.eq(uart.rx.stb),
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
			If(fsm.ongoing("RECEIVE_ADDRESS") & uart.rx.stb,
					address.eq(Cat(uart.rx.dat, address[0:24]))
			)

		###
		data = Signal(32)

		###
		fsm.act("RECEIVE_DATA",
			word_cnt.inc.eq(uart.rx.stb),
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
			word_cnt.inc.eq(uart.tx.ack),
			If(word_cnt.value == 4, 
				burst_cnt.inc.eq(1),
				If(burst_cnt.value == (burst_length-1),
					NextState("WAIT_CMD")
				).Else(
					NextState("READ_DATA")
				)
			),
			uart.tx.stb.eq(1),
			chooser(data, word_cnt.value, uart.tx.dat, n=4, reverse=True)
		)

		###
		self.sync += \
			If(fsm.ongoing("RECEIVE_DATA") & uart.rx.stb,
				data.eq(Cat(uart.rx.dat, data[0:24]))
			).Elif(fsm.ongoing("READ_DATA") & self.wishbone.stb & self.wishbone.ack,
				data.eq(self.wishbone.dat_r)
			)

