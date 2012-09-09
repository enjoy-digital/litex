# De0Nano-System On Chip / Generic Base for a Custom SOC
# - Lm32 SoftCore
# - 32MB Sdram
# - 2KB Eeprom			(TBD)
# - G Sensor & AD Converter	(TBD)
# - Up to 72 GPIO		(8 in/ 8 out)
# - Uart
# - Spi Slave & Master		(Only Master)

#==============================================================================
#	I M P O R T 
#==============================================================================
from fractions import Fraction
from math import ceil

from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import wishbone, csr, wishbone2csr, fml

from soc import lm32, uart, rc5, gpio, spi_master, identifier, fmlbrg, hpdmc_sdr16
from cmacros import get_macros
from timings import *
from constraints import Constraints

#==============================================================================
#	P A R A M E T E R S
#==============================================================================

#Timings Param
clk_freq	= 50*MHz
clk_period_ns	= clk_freq*ns
n		= t2n(clk_period_ns)

#==============================================================================
#	S O C
#==============================================================================

#
# Configuration
#===============================================================================

# Csr
csr_macros = get_macros("common/csrbase.h")
def csr_offset(name):
	base = int(csr_macros[name + "_BASE"], 0)
	assert((base >= 0xe0000000) and (base <= 0xe0010000))
	return (base - 0xe0000000)//0x800
	
# Interrupt
interrupt_macros = get_macros("common/interrupt.h")
def interrupt_n(name):
	return int(interrupt_macros[name + "_INTERRUPT"], 0)
	
# Version
version = get_macros("common/version.h")["VERSION"][1:-1]

def get():
	
	#
	# Wishbone
	#===============================================================================
	cpu0		= lm32.LM32()
	wishbone2csr0	= wishbone2csr.WB2CSR()
	fmlbrg0		= fmlbrg.FMLBRG(16)
	hpdmc0		= hpdmc_sdr16.HPDMC_SDR16(13)

	# CSR          0x00000000 (shadow @0x80000000)
	# FML bridge   0x10000000 (shadow @0x90000000)
	wishbonecon = wishbone.InterconnectShared(
		[
		cpu0.ibus,
		cpu0.dbus
		], [
		(binc("000") , wishbone2csr0.wishbone),
		(binc("001") , fmlbrg0.wishbone)
		],
		register=True,
		offset=1)
	#
	# Fml
	#===============================================================================
	fmlcon0 = fml.Interconnect(fmlbrg0.fml,hpdmc0.fml)
	
	#
	# Csr
	#===============================================================================
	uart0		= uart.UART(csr_offset("UART"), clk_freq, baud=115200)
	identifier0	= identifier.Identifier(csr_offset("ID"), 0x1234, version, int(clk_freq))
	rc50		= rc5.RC5(csr_offset("RC5"),clk_freq)
	gpio0		= gpio.GPIO(csr_offset("GPIO"))
	led0		= gpio.GPIO(csr_offset("LED"))
	sw0		= gpio.GPIO(csr_offset("SW"),4)
	spi_master0	= spi_master.SPI_MASTER(csr_offset("SPI_MASTER"))
	csrcon0		= csr.Interconnect(wishbone2csr0.csr, [
								uart0.csr,
								identifier0.bank.interface,
								rc50.csr,
								gpio0.csr,
								led0.csr,
								sw0.csr,
								spi_master0.csr,
								hpdmc0.csr
								])
	
	#
	# Interrupts
	#===============================================================================
	interrupts = Fragment([
		cpu0.interrupt[interrupt_n("UART")].eq(uart0.irq),
		cpu0.interrupt[interrupt_n("RC5")].eq(rc50.irq),
		cpu0.interrupt[interrupt_n("GPIO")].eq(gpio0.irq)
	])
	#
	# HouseKeeping
	#===============================================================================
	frag = autofragment.from_local() + interrupts
	cst = Constraints(uart0, rc50, gpio0, led0, sw0, spi_master0, hpdmc0)
	src_verilog, vns = verilog.convert(frag,
		cst.get_ios(),
		name="soc",
		return_ns=True)
	src_qsf = cst.get_qsf(vns)
	return (src_verilog, src_qsf)