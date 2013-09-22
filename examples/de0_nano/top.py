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
from migen.fhdl.std import *
from migen.bus import csr
from migen.bank import csrgen

from miscope.std.misc import *

from miscope.trigger import Term
from miscope.miio import MiIo
from miscope.mila import MiLa

from miscope.com import uart2csr

from timings import *

#==============================================================================
#	P A R A M E T E R S
#==============================================================================

# Timings Param
clk_freq	= 50*MHz

# Mila Param
mila_width	= 16
mila_depth  = 4096

#==============================================================================
#   M I S C O P E    E X A M P L E
#==============================================================================
class SoC(Module):
	csr_base = 0xe0000000
	csr_map = {
		"miio":					1,
		"mila":					2,
	}

	def __init__(self, platform):
		# MiIo
		self.submodules.miio = MiIo(8)

		# MiLa
		term = Term(mila_width)
		self.submodules.mila = MiLa(mila_width, mila_depth, [term], rle=True)
	
		# Uart2Csr
		self.submodules.uart2csr = uart2csr.Uart2Csr(clk_freq, 115200)
		uart_pads = platform.request("serial")
		self.comb += uart_pads.tx.eq(self.uart2csr.tx)
		self.comb += self.uart2csr.rx.eq(uart_pads.rx)
	
		# Csr Interconnect
		self.submodules.csrbankarray = csrgen.BankArray(self,
			lambda name, memory: self.csr_map[name if memory is None else name + "_" + memory.name_override])
		self.submodules.csrcon = csr.Interconnect(self.uart2csr.csr, self.csrbankarray.get_buses())
		
		# Led
		self.led = Cat(*[platform.request("user_led", i) for i in range(8)])

		# Misc
		self.cnt = Signal(16)
		self.submodules.freqgen = FreqGen(clk_freq, 500*KHz)
		self.submodules.eventgen_rising = EventGen(RISING_EDGE, clk_freq, 100*ns)
		self.submodules.eventgen_falling = EventGen(FALLING_EDGE, clk_freq, 100*ns)
		self.comb += [
			self.eventgen_rising.i.eq(self.freqgen.o),
			self.eventgen_falling.i.eq(self.freqgen.o)
		]


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
			self.mila.sink.stb.eq(1),
			self.mila.sink.dat.eq(Cat(
				self.freqgen.o,
				self.eventgen_rising.o,
				self.eventgen_falling.o,
				self.cnt[8:12])
			)
		]
		self.sync += self.cnt.eq(self.cnt+1)
