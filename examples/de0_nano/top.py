################################################################################
#            _____       _            ____  _     _ _       _ 
#           |   __|___  |_|___ _ _   |    \|_|___|_| |_ ___| |
#           |   __|   | | | . | | |  |  |  | | . | |  _| .'| |
#           |_____|_|_|_| |___|_  |  |____/|_|_  |_|_| |__,|_|
#                     |___|   |___|          |___|
#
#      Copyright 2013 / Florent Kermarrec / florent@enjoy-digital.fr
#
#                        miscope miio example on De0 Nano
#                        --------------------------------
################################################################################

#==============================================================================
#	I M P O R T 
#==============================================================================
from migen.fhdl.structure import *
from migen.fhdl.module import *
from migen.bus import csr

from miscope import miio
from miscope.bridges import uart2csr

from timings import *

#==============================================================================
#	P A R A M E T E R S
#==============================================================================

# Timings Param
clk_freq	= 50*MHz

# Csr Addr
MIIO0_ADDR  = 0x0000

#==============================================================================
#   M I S C O P E    E X A M P L E
#==============================================================================
class SoC(Module):
	def __init__(self):
		# MiIo
		self.submodules.miio = miio.MiIo(MIIO0_ADDR, 8, "IO")
	
		# Uart2Csr
		self.submodules.uart2csr = uart2csr.Uart2Csr(clk_freq, 115200)
	
		# Csr Interconnect
		self.submodules.csrcon = csr.Interconnect(self.uart2csr.csr,
				[
					self.miio.bank.bus
				])
		
		# Led
		self.led = Signal(8)
		
	###
		# Output
		self.comb += self.led.eq(self.miio.o)

		# Input
		self.comb += self.miio.i.eq(0x5A)