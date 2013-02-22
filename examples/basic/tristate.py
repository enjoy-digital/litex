from migen.fhdl.structure import *
from migen.fhdl.specials import Tristate
from migen.fhdl import verilog

n = 6
pad = Signal(n)
o = Signal(n)
oe = Signal()
i = Signal(n)

f = Fragment(specials={Tristate(pad, o, oe, i)})
print(verilog.convert(f, ios={pad, o, oe, i}))
