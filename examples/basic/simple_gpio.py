from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.fhdl import verilog
from migen.genlib.cdc import MultiReg
from migen.bank import description, csrgen

class Example(Module):
	def __init__(self, ninputs=32, noutputs=32):
		r_o = description.CSRStorage(noutputs, atomic_write=True)
		r_i = description.CSRStatus(ninputs)

		self.submodules.bank = csrgen.Bank([r_o, r_i])
		self.gpio_in = Signal(ninputs)
		self.gpio_out  = Signal(ninputs)

		###

		gpio_in_s = Signal(ninputs)
		self.specials += MultiReg(self.gpio_in, gpio_in_s)
		self.comb += [
			self.gpio_out.eq(r_o.storage),
			r_i.status.eq(gpio_in_s)
		]

example = Example()
i = example.bank.bus
v = verilog.convert(example, {i.dat_r, i.adr, i.we, i.dat_w,
	example.gpio_in, example.gpio_out})
print(v)
