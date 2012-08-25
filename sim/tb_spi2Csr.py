from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import csr
from migen.sim.generic import Simulator, PureSimulable, TopLevel
from migen.sim.icarus import Runner
from migen.bus.transactions import *
from migen.bank import description, csrgen
from migen.bank.description import *

import sys
sys.path.append("../")
import spi2Csr

def get_bit(dat, bit):
	return int(dat & (1<<bit) != 0)

def spi_transactions():
	yield TWrite(0x8000,0x00)
	yield TWrite(0x8001,0x01)
	yield TWrite(0x8002,0x02)
	yield TWrite(0x8003,0x03)
	for i in range(100):
		yield None 

class SpiMaster(PureSimulable):
	def __init__(self, spi, generator):
		self.spi = spi
		self.generator = generator
		self.transaction_start = 0
		self.transaction = None
		self.done = False
	
	def do_simulation(self, s):
		a_w = self.spi.a_width
		d_w = self.spi.d_width

		if not self.done:
			if self.transaction is None:
				try:
					self.transaction = next(self.generator)
				except StopIteration:
					self.done = True
					self.transaction = None
				if self.transaction is not None:
					self.transaction_cnt = 0			
			elif isinstance(self.transaction,TWrite):	
			
					# Clk
					if self.transaction_cnt%2:
						s.wr(self.spi.spi_clk, 1)
					else:
						s.wr(self.spi.spi_clk, 0)

					# Mosi Addr
					if self.transaction_cnt < a_w*2:	
						bit = a_w-1-int((self.transaction_cnt)/2)					
						data = get_bit(self.transaction.address, bit)
						s.wr(self.spi.spi_mosi, data)
					# Mosi Data
					elif self.transaction_cnt >= a_w*2 and self.transaction_cnt < a_w*2+d_w*2:
						bit = d_w-1-int((self.transaction_cnt-a_w*2)/2)					
						data = get_bit(self.transaction.data,bit)
						s.wr(self.spi.spi_mosi, data)						
					else:
						s.wr(self.spi.spi_mosi, 0)

					# Cs_n
					if self.transaction_cnt < a_w*2+d_w*2:
						s.wr(self.spi.spi_cs_n,0)
					else:
						s.wr(self.spi.spi_cs_n, 1)
						s.wr(self.spi.spi_clk, 0)
						s.wr(self.spi.spi_mosi, 0)
						self.transaction = None

					# Incr transaction_cnt
					self.transaction_cnt +=1

def main():
	# Csr Slave
	scratch_reg0 = RegisterField("scratch_reg0", 32, reset=0, access_dev=READ_ONLY)
	scratch_reg1 = RegisterField("scratch_reg1", 32, reset=0, access_dev=READ_ONLY)
	scratch_reg2 = RegisterField("scratch_reg3", 32, reset=0, access_dev=READ_ONLY)
	scratch_reg3 = RegisterField("scratch_reg4", 32, reset=0, access_dev=READ_ONLY)
	regs = [scratch_reg0, scratch_reg1, scratch_reg2, scratch_reg3]
	bank0 = csrgen.Bank(regs,address=0x0000)

	# Spi2Csr
	spi2csr0 = spi2Csr.Spi2Csr(16,8)


	# Csr Interconnect
	csrcon0 = csr.Interconnect(spi2csr0.csr, 
			[
				bank0.interface
			])
	
	# Spi Master
	spi_master0 = SpiMaster(spi2csr0,spi_transactions())

	# Simulation
	def end_simulation(s):
		s.interrupt = spi_master0.done


	fragment = autofragment.from_local()
	fragment += Fragment(sim=[end_simulation])
	sim = Simulator(fragment, Runner(),TopLevel("tb_spi2Csr.vcd"))
	sim.run(1000)

main()
input()	
