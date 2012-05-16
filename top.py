from fractions import Fraction
from math import ceil

from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import wishbone, wishbone2asmi, csr, wishbone2csr, dfi

from milkymist import m1crg, lm32, norflash, uart, sram, s6ddrphy, dfii, asmicon, identifier
from cmacros import get_macros
from constraints import Constraints

MHz = 1000000
clk_freq = (83 + Fraction(1, 3))*MHz
sram_size = 4096 # in bytes
l2_size = 8192 # in bytes

clk_period_ns = 1000000000/clk_freq
def ns(t, margin=True):
	if margin:
		t += clk_period_ns/2
	return ceil(t/clk_period_ns)

sdram_phy = asmicon.PhySettings(
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
	tRCD=ns(15),
	tWR=ns(15),
	tREFI=ns(7800, False),
	tRFC=ns(70),
	
	CL=3,
	rd_delay=4,

	slot_time=16,
	read_time=32,
	write_time=16
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

csr_macros = get_macros("common/csrbase.h")
def csr_offset(name):
	base = int(csr_macros[name + "_BASE"], 0)
	assert((base >= 0xe0000000) and (base <= 0xe0010000))
	return (base - 0xe0000000)//0x800

version = get_macros("common/version.h")["VERSION"][1:-1]

def get():
	#
	# ASMI
	#
	asmicon0 = asmicon.ASMIcon(sdram_phy, sdram_geom, sdram_timing)
	asmiport_wb = asmicon0.hub.get_port()
	asmicon0.finalize()
	
	#
	# DFI
	#
	ddrphy0 = s6ddrphy.S6DDRPHY(sdram_geom.mux_a, sdram_geom.bank_a, sdram_phy.dfi_d)
	dfii0 = dfii.DFIInjector(csr_offset("DFII"),
		sdram_geom.mux_a, sdram_geom.bank_a, sdram_phy.dfi_d, sdram_phy.nphases)
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
	uart0 = uart.UART(csr_offset("UART"), clk_freq, baud=115200)
	identifier0 = identifier.Identifier(csr_offset("ID"), 0x4D31, version)
	csrcon0 = csr.Interconnect(wishbone2csr0.csr, [
		uart0.bank.interface,
		dfii0.bank.interface,
		identifier0.bank.interface
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
	cst = Constraints(crg0, norflash0, uart0, ddrphy0)
	src_verilog, vns = verilog.convert(frag,
		cst.get_ios(),
		name="soc",
		clk_signal=crg0.sys_clk,
		rst_signal=crg0.sys_rst,
		return_ns=True)
	src_ucf = cst.get_ucf(vns)
	return (src_verilog, src_ucf)
