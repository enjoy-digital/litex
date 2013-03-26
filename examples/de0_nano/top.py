################################################################################
#            _____       _            ____  _     _ _       _ 
#           |   __|___  |_|___ _ _   |    \|_|___|_| |_ ___| |
#           |   __|   | | | . | | |  |  |  | | . | |  _| .'| |
#           |_____|_|_|_| |___|_  |  |____/|_|_  |_|_| |__,|_|
#                     |___|   |___|          |___|
#
#      Copyright 2013 / Florent Kermarrec / florent@enjoy-digital.fr
#
#                           miscope example on De0 Nano
#                        --------------------------------
################################################################################

#==============================================================================
#	I M P O R T 
#==============================================================================
from migen.fhdl.structure import *
from migen.fhdl.module import *
from migen.bus import csr

from miscope import trigger, recorder, miio, mila
from miscope.bridges import uart2csr
from miscope.tools.misc import *

from timings import *

#==============================================================================
#	P A R A M E T E R S
#==============================================================================

# Timings Param
clk_freq	= 50*MHz

# Csr Addr
MIIO_ADDR 	= 0x00
MILA_ADDR 	= 0x01

# Mila Param
trig_w		= 16
dat_w		= 16
rec_size	= 4096

#==============================================================================
#   M I S C O P E    E X A M P L E
#==============================================================================
class SoC(Module):
	def __init__(self, platform):
		# MiIo
		self.submodules.miio = miio.MiIo(MIIO_ADDR, 8, "IO")

		# MiLa
		self.submodules.term = trigger.Term(trig_w)
		self.submodules.trigger = trigger.Trigger(trig_w, [self.term])
		self.submodules.recorder = recorder.Recorder(dat_w, rec_size)

		self.submodules.mila = mila.MiLa(MILA_ADDR, self.trigger, self.recorder)
	
		# Uart2Csr
		self.submodules.uart2csr = uart2csr.Uart2Csr(clk_freq, 115200)
		uart_pads = platform.request("serial")
		self.comb += uart_pads.tx.eq(self.uart2csr.tx)
		self.comb += self.uart2csr.rx.eq(uart_pads.rx)
	
		# Csr Interconnect
		self.submodules.csrcon = csr.Interconnect(self.uart2csr.csr,
				[
					self.miio.bank.bus,
					self.trigger.bank.bus,
					self.recorder.bank.bus
				])
		
		# Led
		self.led = platform.request("user_led", 0, 8)

		# Misc
		self.cnt = Signal(9)
		self.submodules.freqgen = FreqGen(clk_freq, 500*KHz)
		self.submodules.eventgen_rising = EventGen(self.freqgen.o, RISING_EDGE, clk_freq, 100*ns)
		self.submodules.eventgen_falling = EventGen(self.freqgen.o, FALLING_EDGE, clk_freq, 100*ns)

	###

		#
		# Miio
		#

		# Output
		self.comb += self.led.eq(self.miio.o)
		
		# Input
		self.comb += self.miio.i.eq(self.miio.o)

		#
		# Mila
		#
		self.comb +=[
			self.mila.trig[0].eq(self.freqgen.o),
			self.mila.trig[1].eq(self.eventgen_rising.o),
			self.mila.trig[2].eq(self.eventgen_falling.o),
			self.mila.trig[3:11].eq(self.cnt),
			self.mila.dat[0].eq(self.freqgen.o),
			self.mila.dat[1].eq(self.eventgen_rising.o),
			self.mila.dat[2].eq(self.eventgen_falling.o),
			self.mila.dat[3:11].eq(self.cnt),
		]
		self.sync += self.cnt.eq(self.cnt+1)
