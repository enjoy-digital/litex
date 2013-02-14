from migen.fhdl.structure import *
from migen.fhdl import verilog

n = 6
pad = Signal(n)
o = Signal(n)
oe = Signal()
i = Signal(n)

f = Fragment(tristates={Tristate(pad, o, oe, i)})
print(verilog.convert(f, ios={pad, o, oe, i}))
