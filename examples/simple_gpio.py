from migen.fhdl.structure import *
from migen.fhdl import verilog
from migen.bank import description, csrgen

ninputs = 4
noutputs = 31

oreg = description.RegisterField("o", noutputs)
ireg = description.RegisterRaw("i", ninputs)

# input path
gpio_in = Signal(BV(ninputs))
gpio_in_s = Signal(BV(ninputs)) # synchronizer
insync = [gpio_in_s.eq(gpio_in), ireg.w.eq(gpio_in_s)]
inf = Fragment(sync=insync)

bank = csrgen.Bank([oreg, ireg])
f = bank.get_fragment() + inf
oreg.field.r.name_override = "gpio_out"
i = bank.interface
v = verilog.convert(f, {i.d_o, oreg.field.r, i.a_i, i.we_i, i.d_i, gpio_in})
print(v)
