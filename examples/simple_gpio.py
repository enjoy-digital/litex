from migen.fhdl.structure import *
from migen.fhdl import verilog
from migen.bank import description, csrgen

ninputs = 4
noutputs = 4

oreg = description.Register("o")
ofield = description.Field(oreg, "val", noutputs)
ireg = description.Register("i")
ifield = description.Field(ireg, "val", ninputs, description.READ_ONLY, description.WRITE_ONLY)

# input path
gpio_in = Signal(BV(ninputs))
gpio_in_s = Signal(BV(ninputs)) # synchronizer
incomb = [ifield.dev_we.eq(1)]
insync = [gpio_in_s.eq(gpio_in), ifield.dev_w.eq(gpio_in_s)]
inf = Fragment(incomb, insync)

bank = csrgen.Bank([oreg, ireg])
f = bank.get_fragment() + inf
i = bank.interface
ofield.dev_r.name = "gpio_out"
v = verilog.convert(f, {i.d_o, ofield.dev_r, i.a_i, i.we_i, i.d_i, gpio_in})
print(v)
