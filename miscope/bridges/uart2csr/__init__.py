from migen.fhdl.structure import *
from migen.fhdl.module import *
from migen.bus import csr
from migen.genlib.fsm import *

from miscope.bridges.uart2csr.uart import *

WRITE_CMD = 0x01
READ_CMD = 0x02
CLOSE_CMD = 0x03

class Uart2Csr(Module):
	def __init__(self, clk_freq, baud):
		# Uart interface
		self.rx = Signal()
		self.tx = Signal()
		
		# Csr interface
		self.csr = csr.Interface(32, 8)
		
	###
		
		self.submodules.uart = UART(clk_freq, baud)
		uart = self.uart

		#
		# In/Out
		#
		self.comb +=[
			uart.rx.eq(self.rx),
			self.tx.eq(uart.tx)
		]

		cmd = Signal(8)
		cnt = Signal(3)
		sr = Signal(32)
		burst_cnt = Signal(8)
		addr = Signal(32)
		data = Signal(8)

		# FSM
		self.submodules.fsm = FSM("IDLE", 
								  "GET_BL", "GET_ADDR", 
				 				  "GET_DATA", "WRITE_CSR",
				 				  "READ_CSR0", "READ_CSR1", "SEND_DATA")

		fsm = self.fsm

		#
		# Global
		#
		self.sync +=[
			If(fsm.ongoing(fsm.IDLE), cnt.eq(0)
			).Elif(uart.rx_ev, cnt.eq(cnt + 1)),

			If(uart.rx_ev, sr.eq(Cat(uart.rx_dat, sr[0:24])))
		]

		# State done signals
		get_bl_done = Signal()
		get_addr_done = Signal()
		get_addr_done_d = Signal()
		get_data_done = Signal()
		send_data_done = Signal()

		#
		# Idle
		#
		fsm.act(fsm.IDLE,
			If(uart.rx_ev & ((uart.rx_dat == WRITE_CMD) | (uart.rx_dat == READ_CMD)),
				fsm.next_state(fsm.GET_BL)
			)
		)

		self.sync += If(fsm.ongoing(fsm.IDLE) & uart.rx_ev, cmd.eq(uart.rx_dat))

		#
		# Get burst length
		#
		fsm.act(fsm.GET_BL,
			If(get_bl_done,
				fsm.next_state(fsm.GET_ADDR)
			)
		)

		self.comb += get_bl_done.eq(uart.rx_ev & fsm.ongoing(fsm.GET_BL))

		self.sync += If(get_bl_done, burst_cnt.eq(uart.rx_dat))

		#
		# Get address
		#
		fsm.act(fsm.GET_ADDR,
			If(get_addr_done & (cmd == WRITE_CMD),
				fsm.next_state(fsm.GET_DATA)
			).Elif(get_addr_done & (cmd == READ_CMD),
				fsm.next_state(fsm.READ_CSR0)
			)	
		)

		self.comb += get_addr_done.eq(uart.rx_ev & (cnt == 4) & fsm.ongoing(fsm.GET_ADDR))
		self.sync += get_addr_done_d.eq(get_addr_done)
		
		self.sync += [
			If(get_addr_done_d,
				addr.eq(sr)
			).Elif(fsm.leaving(fsm.WRITE_CSR) | send_data_done,
				addr.eq(addr + 1)
			)
		]

		#
		# Get data
		#
		fsm.act(fsm.GET_DATA,
			If(get_data_done,
				fsm.next_state(fsm.WRITE_CSR)
			)
		)

		self.comb += get_data_done.eq(uart.rx_ev & fsm.ongoing(fsm.GET_DATA))	
		self.sync += [
			If(get_data_done,
				burst_cnt.eq(burst_cnt-1),
				data.eq(uart.rx_dat)
			)
		]

		#
		# Write Csr
		#
		fsm.act(fsm.WRITE_CSR,
			If((burst_cnt==0), 
				fsm.next_state(fsm.IDLE)
			).Else(fsm.next_state(fsm.GET_DATA))
		)


		#
		# Read Csr0
		#
		fsm.act(fsm.READ_CSR0,
			fsm.next_state(fsm.READ_CSR1)
		)

		self.sync += If(fsm.entering(fsm.READ_CSR0), burst_cnt.eq(burst_cnt-1))

		#
		# Read Csr1
		#
		fsm.act(fsm.READ_CSR1,
			fsm.next_state(fsm.SEND_DATA)
		)


		#
		# Send Data
		#
		fsm.act(fsm.SEND_DATA,
			If(send_data_done & (burst_cnt==0),
				fsm.next_state(fsm.IDLE)
			).Elif(send_data_done,
				fsm.next_state(fsm.READ_CSR0)
			)
		)

		self.comb += send_data_done.eq(fsm.ongoing(fsm.SEND_DATA) & uart.tx_ev)

		self.sync += [
				uart.tx_dat.eq(self.csr.dat_r),
				uart.tx_we.eq(fsm.entering(fsm.SEND_DATA)),
		]


		#
		# Csr access
		#
		self.comb += self.csr.adr.eq(addr) 
		self.sync +=[
			self.csr.dat_w.eq(data),
			If(fsm.ongoing(fsm.WRITE_CSR),
				self.csr.we.eq(1)
			).Else(
				self.csr.we.eq(0)	
			)
		]