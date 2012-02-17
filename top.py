from fractions import Fraction

from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import wishbone, asmibus, wishbone2asmi, csr, wishbone2csr

from milkymist import m1crg, lm32, norflash, uart, sram, s6ddrphy
import constraints

MHz = 1000000
clk_freq = (83 + Fraction(1, 3))*MHz
sram_size = 4096 # in bytes
l2_size = 8192 # in bytes

def ddrphy_clocking(crg, phy):
	names = [
		"clk2x_90",
		"clk4x_wr_left",
		"clk4x_wr_strb_left",
		"clk4x_wr_right",
		"clk4x_wr_strb_right",
		"clk4x_rd_left",
		"clk4x_rd_strb_left",
		"clk4x_rd_right",
		"clk4x_rd_strb_right",
	]
	comb = [getattr(phy, name).eq(getattr(crg, name)) for name in names]
	return Fragment(comb)

def get():
	#
	# ASMI
	#
	ddrphy0 = s6ddrphy.S6DDRPHY(13, 2, 128)
	asmihub0 = asmibus.Hub(23, 128, 12) # TODO: get hub from memory controller
	asmiport_wb = asmihub0.get_port()
	asmihub0.finalize()
	
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
	csrcon0 = csr.Interconnect(wishbone2csr0.csr, [uart0.bank.interface])
	
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
