from migen.fhdl.structure import *
from migen.bus import csr
from migen.bank import description, csrgen
from migen.bank.description import *

class Spi2Csr : 
	def __init__(self, a_width, d_width, max_burst = 8):
		self.a_width = a_width
		self.d_width = d_width
		self.max_burst = 8
		# Csr interface
		self.csr = csr.Interface(self.a_width, self.d_width)
		# Spi interface
		self.spi_clk = Signal()
		self.spi_cs_n = Signal(reset=1)
		self.spi_mosi = Signal()
		self.spi_miso = Signal()
		self.spi_int_n = Signal(reset=1)
		
	def get_fragment(self):
		comb = []
		sync = []
		
		# Resychronisation
		spi_clk_d1 = Signal()
		spi_clk_d2 = Signal()
		spi_clk_d3 = Signal()
		
		sync += [
			spi_clk_d1.eq(self.spi_clk),
			spi_clk_d2.eq(spi_clk_d1),
			spi_clk_d3.eq(spi_clk_d2)
		]
		
		spi_cs_n_d1 = Signal()
		spi_cs_n_d2 = Signal()
		spi_cs_n_d3 = Signal()
		
		sync += [
			spi_cs_n_d1.eq(self.spi_cs_n),
			spi_cs_n_d2.eq(spi_cs_n_d1),
			spi_cs_n_d3.eq(spi_cs_n_d2)
		]
		
		spi_mosi_d1 = Signal()
		spi_mosi_d2 = Signal()
		spi_mosi_d3 = Signal()
		
		sync += [
			spi_mosi_d1.eq(self.spi_mosi),
			spi_mosi_d2.eq(spi_mosi_d1),
			spi_mosi_d3.eq(spi_mosi_d2)
		]
		
		# Decode
		spi_clk_rising = Signal()
		spi_clk_falling = Signal()
		spi_cs_n_active = Signal()
		spi_mosi_dat = Signal()
		
		comb += [
			spi_clk_rising.eq(spi_clk_d2 & ~spi_clk_d3),
			spi_clk_falling.eq(~spi_clk_d2 & spi_clk_d3),
			spi_cs_n_active.eq(~spi_cs_n_d3),
			spi_mosi_dat.eq(spi_mosi_d3)
		]
		
		#
		# Spi --> Csr
		#
		spi_cnt = Signal(bits_for(self.a_width+self.max_burst*self.d_width))
		spi_addr = Signal(self.a_width)
		spi_w_dat = Signal(self.d_width)
		spi_r_dat = Signal(self.d_width)
		spi_we = Signal()
		spi_re = Signal()
		spi_we_re_done = Signal(reset = 1)
		spi_miso_dat = Signal()
		
		# Re/We Signals Decoding
		first_b = Signal()
		last_b = Signal()
		
		comb +=[
			first_b.eq(spi_cnt[0:bits_for(self.d_width)-1] == 0),
			last_b.eq(spi_cnt[0:bits_for(self.d_width)-1] == 2**(bits_for(self.d_width)-1)-1)
		]
		sync +=[
			If((spi_cnt >= (self.a_width + self.d_width)) & first_b,
				spi_we.eq(spi_addr[self.a_width-1] & ~spi_we_re_done),
				spi_re.eq(~spi_addr[self.a_width-1] & ~spi_we_re_done),
				spi_we_re_done.eq(1)
			).Elif((spi_cnt >= self.a_width) & first_b,
				spi_re.eq(~spi_addr[self.a_width-1] & ~spi_we_re_done),
				spi_we_re_done.eq(1)
			).Else(
				spi_we.eq(0),
				spi_re.eq(0),
				spi_we_re_done.eq(0)
			)
		]
		
		# Spi Addr / Data Decoding
		sync +=[
			If(~spi_cs_n_active,
				spi_cnt.eq(0),
			).Elif(spi_clk_rising,
				# addr
				If(spi_cnt < self.a_width,
					spi_addr.eq(Cat(spi_mosi_dat,spi_addr[:self.a_width-1]))
				).Elif((spi_cnt >= (self.a_width+self.d_width)) & last_b,
					spi_addr.eq(spi_addr+1)
				).Elif((spi_cnt >= self.a_width) & last_b & (spi_addr[self.a_width-1] == 0),
					spi_addr.eq(spi_addr+1)
				),
				# dat
				If(spi_cnt >= self.a_width,
					spi_w_dat.eq(Cat(spi_mosi_dat,spi_w_dat[:self.d_width-1]))
				),
				
				# spi_cnt
				spi_cnt.eq(spi_cnt+1)
			)
		]
		
		#
		# Csr --> Spi
		#
		spi_r_dat_shift = Signal(self.d_width)
		sync +=[
			If(spi_re,
				spi_r_dat_shift.eq(spi_r_dat)
			),
			
			If(~spi_cs_n_active,
				spi_miso_dat.eq(0)
			).Elif(spi_clk_falling,
				spi_miso_dat.eq(spi_r_dat_shift[self.d_width-1]),
				spi_r_dat_shift.eq(Cat(0,spi_r_dat_shift[:self.d_width-1]))
			)
			]
			
		
		#
		# Csr Interface
		#
		comb += [
			self.csr.adr.eq(spi_addr),
			self.csr.dat_w.eq(spi_w_dat),
			self.csr.we.eq(spi_we)
		]
		
		#
		# Spi Interface
		#
		comb += [
			spi_r_dat.eq(self.csr.dat_r),
			self.spi_miso.eq(spi_miso_dat)
		]
		return Fragment(comb=comb,sync=sync)