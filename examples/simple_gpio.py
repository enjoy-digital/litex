from migen.fhdl import structure as f
from migen.fhdl import verilog
from migen.bank import description, csrgen

ninputs = 4
noutputs = 4

oreg = description.Register("o")
ofield = description.Field(oreg, "val", noutputs)
ireg = description.Register("i")
ifield = description.Field(ireg, "val", ninputs, description.READ_ONLY, description.WRITE_ONLY)

# input path
gpio_in = f.Signal(f.BV(ninputs), name="gpio_in")
gpio_in_s = f.Signal(f.BV(ninputs), name="gpio_in_s") # synchronizer
incomb = [f.Assign(ifield.dev_we, 1)]
insync = [f.Assign(gpio_in_s, gpio_in), f.Assign(ifield.dev_w, gpio_in_s)]
inf = f.Fragment(incomb, insync)

bank = csrgen.Bank([oreg, ireg])
f = bank.GetFragment() + inf
i = bank.interface
ofield.dev_r.name = "gpio_out"
v = verilog.Convert(f, {i.d_o, ofield.dev_r, i.a_i, i.we_i, i.d_i, gpio_in})
print(v)