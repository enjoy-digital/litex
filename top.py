from migen.fhdl.structure import *
from migen.fhdl import convtools, verilog, autofragment
from migen.bus import wishbone, csr, wishbone2csr

from milkymist import m1reset, lm32, norflash, uart
import constraints

def get():
	reset0 = m1reset.Inst()
	
	cpu0 = lm32.Inst()
	norflash0 = norflash.Inst(25, 12)
	wishbone2csr0 = wishbone2csr.Inst()
	wishbonecon0 = wishbone.InterconnectShared(
		[cpu0.ibus, cpu0.dbus],
		[(0, norflash0.bus), (3, wishbone2csr0.wishbone)],
		register=True,
		offset=1)
	uart0 = uart.Inst(0, 50*1000*1000, baud=115200)
	csrcon0 = csr.Interconnect(wishbone2csr0.csr, [uart0.bus])
	
	frag = autofragment.from_local() + Fragment(pads={reset0.trigger_reset})
	vns = convtools.Namespace()
	src_verilog = verilog.Convert(frag, name="soc",
		rst_signal=reset0.sys_rst,
		ns=vns)
	src_ucf = constraints.get(vns, reset0, norflash0, uart0)
	return (src_verilog, src_ucf)
