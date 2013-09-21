from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.genlib.cdc import MultiReg
from migen.bank.description import *
from migen.bank.eventmanager import *

class UART(Module):
	def __init__(self, clk_freq, baud=115200):
		
		self.rx_ev = Signal()
		self.rx_dat = Signal(8)
		
		self.tx_we = Signal()
		self.tx_ev = Signal()
		self.tx_dat = Signal(8)
		
		self.divisor = Signal(16, reset=int(clk_freq/baud/16))

		self.tx = Signal(reset=1)
		self.rx = Signal()

	
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
		tx_done = self.tx_ev
		tx_busy = Signal()
		self.sync += [
			tx_done.eq(0),
			If(self.tx_we,
				tx_reg.eq(self.tx_dat),
				tx_bitcount.eq(0),
				tx_count16.eq(1),
				tx_busy.eq(1),
				self.tx.eq(0)
			).Elif(enable16 & tx_busy,
				tx_count16.eq(tx_count16 + 1),
				If(tx_count16 == 0,
					tx_bitcount.eq(tx_bitcount + 1),
					If(tx_bitcount == 8,
						self.tx.eq(1)
					).Elif(tx_bitcount == 9,
						self.tx.eq(1),
						tx_busy.eq(0),
						tx_done.eq(1)
					).Else(
						self.tx.eq(tx_reg[0]),
						tx_reg.eq(Cat(tx_reg[1:], 0))
					)
				)
			)
		]
		
		# RX
		rx = Signal()
		self.specials += MultiReg(self.rx, rx, "sys")
		rx_r = Signal()
		rx_reg = Signal(8)
		rx_bitcount = Signal(4)
		rx_count16 = Signal(4)
		rx_busy = Signal()
		rx_done = self.rx_ev
		rx_data = self.rx_dat
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
