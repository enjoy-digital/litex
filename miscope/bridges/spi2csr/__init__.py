from migen.fhdl.structure import *
from migen.genlib.misc import *
from migen.genlib.cdc import *
from migen.bus import csr

class Spi2Csr(Module):
	def __init__(self, burst_length=8):
		self.a_w = 14
		self.d_w = 8
		self.burst_length = 8
		
		# Csr interface
		self.csr = csr.Interface()
		
		# Spi interface
		self.spi_clk = Signal()
		self.spi_cs_n = Signal(reset=1)
		self.spi_mosi = Signal()
		self.spi_miso = Signal()
		
	###
		
		# Resychronisation
		clk_synchro = Synchronizer(i=self.spi_clk)
		cs_n_synchro = Synchronizer(i=self.spi_cs_n)
		mosi_synchro = Synchronizer(i=self.spi_mosi)

		self.specials += {clk_synchro, cs_n_synchro, mosi_synchro}

		# Decode
		spi_clk_rising = Signal()
		spi_clk_falling = Signal()
		spi_cs_n_active = Signal()
		spi_mosi_dat = Signal()
		
		self.specials += RisingEdge(i=clk_synchro.o, o=spi_clk_rising)
		self.specials += FallingEdge(i=clk_synchro.o, o=spi_clk_falling)

		self.sync +=[
			spi_cs_n_active.eq(~cs_n_synchro.o),
			spi_mosi_dat.eq(~mosi_synchro.o),
		]
		
		#
		# Spi --> Csr
		#
		spi_cnt = Signal(bits_for(self.a_w + self.burst_length*self.d_w))
		spi_addr = Signal(self.a_w)
		spi_w_dat = Signal(self.d_w)
		spi_r_dat = Signal(self.d_w)
		spi_we = Signal()
		spi_re = Signal()
		spi_we_re_done = Signal(reset=1)
		spi_miso_dat = Signal()
		
		# Re/We Signals Decoding
		first_b = Signal()
		last_b = Signal()
		
		self.comb +=[
			first_b.eq(spi_cnt[0:bits_for(self.d_w)-1] == 0),
			last_b.eq(spi_cnt[0:bits_for(self.d_w)-1] == 2**(bits_for(self.d_w-1))-1)
		]
		self.sync +=[
			If((spi_cnt >= (self.a_w + self.d_w)) & first_b,
				spi_we.eq(spi_addr[self.a_w-1] & ~spi_we_re_done),
				spi_re.eq(~spi_addr[self.a_w-1] & ~spi_we_re_done),
				spi_we_re_done.eq(1)
			).Elif((spi_cnt >= self.a_w) & first_b,
				spi_re.eq(~spi_addr[self.a_w-1] & ~spi_we_re_done),
				spi_we_re_done.eq(1)
			).Else(
				spi_we.eq(0),
				spi_re.eq(0),
				spi_we_re_done.eq(0)
			)
		]
		
		# Spi Addr / Data Decoding
		self.sync +=[
			If(~spi_cs_n_active,
				spi_cnt.eq(0),
			).Elif(spi_clk_rising,
				# addr
				If(spi_cnt < self.a_w,
					spi_addr.eq(Cat(spi_mosi_dat,spi_addr[:self.a_w-1]))
				).Elif((spi_cnt >= (self.a_w+self.d_w)) & last_b,
					spi_addr.eq(spi_addr+1)
				).Elif((spi_cnt >= self.a_w) & last_b & (spi_addr[self.a_w-1] == 0),
					spi_addr.eq(spi_addr+1)
				),
				# dat
				If(spi_cnt >= self.a_w,
					spi_w_dat.eq(Cat(spi_mosi_dat,spi_w_dat[:self.d_w-1]))
				),
				
				# spi_cnt
				spi_cnt.eq(spi_cnt+1)
			)
		]
		
		#
		# Csr --> Spi
		#
		spi_r_dat_shift = Signal(self.d_w)
		self.sync +=[
			If(spi_re,
				spi_r_dat_shift.eq(spi_r_dat)
			),
			
			If(~spi_cs_n_active,
				spi_miso_dat.eq(0)
			).Elif(spi_clk_falling,
				spi_miso_dat.eq(spi_r_dat_shift[self.d_w-1]),
				spi_r_dat_shift.eq(Cat(0,spi_r_dat_shift[:self.d_w-1]))
			)
		]
			
		
		#
		# Csr Interface
		#
		self.comb += [
			self.csr.adr.eq(spi_addr),
			self.csr.dat_w.eq(spi_w_dat),
			self.csr.we.eq(spi_we)
		]
		
		#
		# Spi Interface
		#
		self.comb += [
			spi_r_dat.eq(self.csr.dat_r),
			self.spi_miso.eq(spi_miso_dat)
		]