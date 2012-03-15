from fractions import Fraction
from math import ceil

from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import wishbone, wishbone2asmi, csr, wishbone2csr, dfi

from milkymist import m1crg, lm32, norflash, uart, sram, s6ddrphy, dfii, asmicon
import constraints

MHz = 1000000
clk_freq = (83 + Fraction(1, 3))*MHz
sram_size = 4096 # in bytes
l2_size = 8192 # in bytes

clk_period_ns = 1000000000/clk_freq
def ns(t, margin=False):
	if margin:
		t += clk_period_ns/2
	return ceil(t/clk_period_ns)

sdram_phy = asmicon.PhySettings(
	dfi_a=13,
	dfi_d=64, 
	nphases=2,
	rdphase=0,
	wrphase=1
)
sdram_geom = asmicon.GeomSettings(
	bank_a=2,
	row_a=13,
	col_a=10
)
sdram_timing = asmicon.TimingSettings(
	tRP=ns(15),
	tREFI=ns(7800),
	tRFC=ns(70)
)

def ddrphy_clocking(crg, phy):
	names = [
		"clk2x_270",
		"clk4x_wr",
		"clk4x_wr_strb",
		"clk4x_rd",
		"clk4x_rd_strb"
	]
	comb = [getattr(phy, name).eq(getattr(crg, name)) for name in names]
	return Fragment(comb)

def get():
	#
	# ASMI
	#
	asmicon0 = asmicon.ASMIcon(sdram_phy, sdram_geom, sdram_timing, 8)
	asmiport_wb = asmicon0.hub.get_port()
	asmicon0.finalize()
	
	#
	# DFI
	#
	ddrphy0 = s6ddrphy.S6DDRPHY(sdram_phy.dfi_a, sdram_geom.bank_a, sdram_phy.dfi_d)
	dfii0 = dfii.DFIInjector(1, sdram_phy.dfi_a, sdram_geom.bank_a, sdram_phy.dfi_d, sdram_phy.nphases)
	dficon0 = dfi.Interconnect(dfii0.master, ddrphy0.dfi)
	dficon1 = dfi.Interconnect(asmicon0.dfi, dfii0.slave)

	#
	# WISHBONE
	#
	cpu0 = lm32.LM32()
	norflash0 = norflash.NorFlash(25, 12)
	sram0 = sram.SRAM(sram_size//4)
	wishbone2asmi0 = wishbone2asmi.WB2ASMI(l2_size//4, asmiport_wb)
	wishbone2csr0 = wishbone2csr.WB2CSR()
	
	# norflash     0x00000000 (shadow @0x80000000)
	# SRAM/debug   0x10000000 (shadow @0x90000000)
	# USB          0x20000000 (shadow @0xa0000000)
	# Ethernet     0x30000000 (shadow @0xb0000000)
	# SDRAM        0x40000000 (shadow @0xc0000000)
	# CSR bridge   0x60000000 (shadow @0xe0000000)
	wishbonecon0 = wishbone.InterconnectShared(
		[
			cpu0.ibus,
			cpu0.dbus
		], [
			(binc("000"), norflash0.bus),
			(binc("001"), sram0.bus),
			(binc("10"), wishbone2asmi0.wishbone),
			(binc("11"), wishbone2csr0.wishbone)
		],
		register=True,
		offset=1)
	
	#
	# CSR
	#
	uart0 = uart.UART(0, clk_freq, baud=115200)
	csrcon0 = csr.Interconnect(wishbone2csr0.csr, [
		uart0.bank.interface,
		dfii0.bank.interface
	])
	
	#
	# Interrupts
	#
	interrupts = Fragment([
		cpu0.interrupt[0].eq(uart0.events.irq)
	])
	
	#
	# Housekeeping
	#
	crg0 = m1crg.M1CRG(50*MHz, clk_freq)
	
	frag = autofragment.from_local() + interrupts + ddrphy_clocking(crg0, ddrphy0)
	src_verilog, vns = verilog.convert(frag,
		{crg0.trigger_reset},
		name="soc",
		clk_signal=crg0.sys_clk,
		rst_signal=crg0.sys_rst,
		return_ns=True)
	src_ucf = constraints.get(vns, crg0, norflash0, uart0, ddrphy0)
	return (src_verilog, src_ucf)
