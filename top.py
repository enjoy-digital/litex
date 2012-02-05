from migen.fhdl.structure import *
from migen.fhdl import tools, verilog, autofragment
from migen.bus import wishbone, csr, wishbone2csr

from milkymist import m1reset, clkfx, lm32, norflash, uart, sram
import constraints

def get():
	MHz = 1000000
	clk_freq = 80*MHz
	sram_size = 4096 # in kilobytes
	
	clkfx_sys = clkfx.ClkFX(50*MHz, clk_freq)
	reset0 = m1reset.M1Reset()
	
	cpu0 = lm32.LM32()
	norflash0 = norflash.NorFlash(25, 12)
	sram0 = sram.SRAM(sram_size//4)
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
			(binc("11"), wishbone2csr0.wishbone)
		],
		register=True,
		offset=1)
	
	uart0 = uart.UART(0, clk_freq, baud=115200)
	csrcon0 = csr.Interconnect(wishbone2csr0.csr, [uart0.bank.interface])
	
	frag = autofragment.from_local()
	src_verilog, vns = verilog.convert(frag,
		{clkfx_sys.clkin, reset0.trigger_reset},
		name="soc",
		clk_signal=clkfx_sys.clkout,
		rst_signal=reset0.sys_rst,
		return_ns=True)
	src_ucf = constraints.get(vns, clkfx_sys, reset0, norflash0, uart0)
	return (src_verilog, src_ucf)
