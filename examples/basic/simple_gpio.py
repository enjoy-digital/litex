from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.fhdl import verilog
from migen.genlib.cdc import MultiReg
from migen.bank import description, csrgen
from migen.bank.description import READ_ONLY, WRITE_ONLY

class Example(Module):
	def __init__(self, ninputs=32, noutputs=32):
		r_o = description.RegisterField(noutputs, atomic_write=True)
		r_i = description.RegisterField(ninputs, READ_ONLY, WRITE_ONLY)

		self.submodules.bank = csrgen.Bank([r_o, r_i])
		self.gpio_in = Signal(ninputs)
		self.gpio_out  = Signal(ninputs)

		###

		gpio_in_s = Signal(ninputs)
		self.specials += MultiReg(self.gpio_in, gpio_in_s, "sys")
		self.comb += [
			r_i.field.w.eq(gpio_in_s),
			self.gpio_out.eq(r_o.field.r)
		]

example = Example()
i = example.bank.bus
v = verilog.convert(example, {i.dat_r, i.adr, i.we, i.dat_w,
	example.gpio_in, example.gpio_out})
print(v)
