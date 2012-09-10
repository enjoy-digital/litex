from migen.fhdl.structure import *
from migen.fhdl import verilog

# convert pulse into level change
i = Signal()
level = Signal()
isync = [If(i, level.eq(~level))]

# synchronize level to oclk domain
slevel = [Signal() for i in range(3)]
osync = [
	slevel[0].eq(level),
	slevel[1].eq(slevel[0]),
	slevel[2].eq(slevel[1])
]

# regenerate pulse
o = Signal()
comb = [o.eq(slevel[1] ^ slevel[2])]

f = Fragment(comb, {"i": isync, "o": osync})
v = verilog.convert(f, ios={i, o})
print(v)
