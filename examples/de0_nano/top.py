################################################################################
#            _____       _            ____  _     _ _       _ 
#           |   __|___  |_|___ _ _   |    \|_|___|_| |_ ___| |
#           |   __|   | | | . | | |  |  |  | | . | |  _| .'| |
#           |_____|_|_|_| |___|_  |  |____/|_|_  |_|_| |__,|_|
#                     |___|   |___|          |___|
#
#      Copyright 2012 / Florent Kermarrec / florent@enjoy-digital.fr
#
#                  miscope example on De0 Nano Board
#                  ----------------------------------
################################################################################
#
# In this example signals are generated in the FPGA. 
# We use miscope to record those signals and visualize them.
# 
# Example architecture:
# ----------------------
#        miscope Config  --> Python Client (Host) --> Vcd Output
#             & Trig                |
#                        Arduino (Uart<-->Spi Bridge)
#                                   |
#                                De0 Nano
#                                   |
#              +--------------------+-----------------------+  
#            miIo             Signal Generator           miLa
#       Control of Signal        Ramp, Sinus,           Logic Analyzer  
#           generator            Square, ...
###############################################################################


#==============================================================================
#	I M P O R T 
#==============================================================================
from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import csr
from migen.bus.transactions import *
from migen.bank import description, csrgen
from migen.bank.description import *

from miscope import trigger, recorder, miio, mila
from miscope.bridges import spi2csr

from timings import *

from math import sin

#==============================================================================
#	P A R A M E T E R S
#==============================================================================

#Timings Param
clk_freq	= 50*MHz
clk_period_ns	= clk_freq*ns
n		= t2n(clk_period_ns)

# Bus Width
trig0_width = 16
dat0_width = 16

trig1_width = 32
dat1_width = 32

# Record Size
record_size = 4096

# Csr Addr
MIIO0_ADDR  = 0x0000
MILA0_ADDR  = 0x0200
MILA1_ADDR  = 0x0600

#==============================================================================
#       M I S C O P E    E X A M P L E
#==============================================================================
class SoC:
	def __init__(self):
		# migIo0
		self.miIo0 = miio.MiIo(MIIO0_ADDR, 8, "IO")
	
		# migLa0
		self.term0 = trigger.Term(trig0_width)
		self.trigger0 = trigger.Trigger(trig0_width, [self.term0])
		self.recorder0 = recorder.Recorder(dat0_width, record_size)
	
		self.miLa0 = mila.MiLa(MILA0_ADDR, self.trigger0, self.recorder0)
	
		# migLa1
		self.term1 = trigger.Term(trig1_width)
		self.trigger1 = trigger.Trigger(trig1_width, [self.term1])
		self.recorder1 = recorder.Recorder(dat1_width, record_size)
	
		self.miLa1 = mila.MiLa(MILA1_ADDR, self.trigger1, self.recorder1)
	
		# Spi2Csr
		self.spi2csr0 = spi2csr.Spi2Csr(16,8)
	
		# Csr Interconnect
		self.csrcon0 = csr.Interconnect(self.spi2csr0.csr, 
				[
					self.miIo0.bank.bus,
					self.miLa0.trigger.bank.bus,
					self.miLa0.recorder.bank.bus,
					self.miLa1.trigger.bank.bus,
					self.miLa1.recorder.bank.bus		
				])
		
		self.clk50 = Signal()
		self.led = Signal(8)		
		self.gpio_2 = Signal(13)
		self.key = Signal(2)
		self.cd_sys = ClockDomain("sys")
		
	def get_fragment(self):			
		comb = []
		sync = []
	
		#
		# Signal Generator
		#
	
		# Counter
		cnt_gen = Signal(8)
		sync += [
			cnt_gen.eq(cnt_gen+1)
		]
	
		# Square
		square_gen = Signal(8)
		sync += [
			If(cnt_gen[7],
				square_gen.eq(255)
			).Else(
				square_gen.eq(0)
			)
		]
	
		sinus = [int(128*sin((2*3.1415)/256*(x+1)))+128 for x in range(256)]
		sinus_re = Signal()
		sinus_gen = Signal(8)
		comb +=[sinus_re.eq(1)]
		sinus_mem = Memory(8, 256, init = sinus)
		sinus_port = sinus_mem.get_port(has_re=True)
		comb += [
			sinus_port.adr.eq(cnt_gen),
			sinus_port.re.eq(sinus_re),
			sinus_gen.eq(sinus_port.dat_r)
		]
	
		# Signal Selection
		sig_gen = Signal(8)
		comb += [
			If(self.miIo0.o == 0,
				sig_gen.eq(cnt_gen)
			).Elif(self.miIo0.o == 1,
				sig_gen.eq(square_gen)
			).Elif(self.miIo0.o == 2,
				sig_gen.eq(sinus_gen)
			).Else(
				sig_gen.eq(0)
			)
		]
	
		# Led
		comb += [self.led.eq(self.miIo0.o[:8])]
	
	
		# MigLa0 input
		comb += [
			self.miLa0.trig.eq(sig_gen),
			self.miLa0.dat.eq(sig_gen)
		]
	
		# MigLa1 input
		comb += [
			self.miLa1.trig[:8].eq(self.spi2csr0.csr.dat_w),
			self.miLa1.trig[8:24].eq(self.spi2csr0.csr.adr),
			self.miLa1.trig[24].eq(self.spi2csr0.csr.we),
			self.miLa1.dat[:8].eq(self.spi2csr0.csr.dat_w),
			self.miLa1.dat[8:24].eq(self.spi2csr0.csr.adr),
			self.miLa1.dat[24].eq(self.spi2csr0.csr.we)
		]
		
		# Spi2Csr
		self.spi2csr0.spi_clk = self.gpio_2[0]
		self.spi2csr0.spi_cs_n = self.gpio_2[1]
		self.spi2csr0.spi_mosi = self.gpio_2[2]
		self.spi2csr0.spi_miso = self.gpio_2[3]
		
	  #
		# Clocking / Reset
		#
		comb += [
			self.cd_sys.clk.eq(self.clk50),
			self.cd_sys.rst.eq(~self.key[0])
			]

		frag = autofragment.from_attributes(self)
		frag += Fragment(comb, sync)
		return frag