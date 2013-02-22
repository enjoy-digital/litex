from migen.fhdl.structure import *
from migen.fhdl.specials import SynthesisDirective
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

# disable shift register extraction
disable_srl = {
	SynthesisDirective("attribute shreg_extract of {signal} is no", signal=slevel[0]),
	SynthesisDirective("attribute shreg_extract of {signal} is no", signal=slevel[1])
}

# regenerate pulse
o = Signal()
comb = [o.eq(slevel[1] ^ slevel[2])]

f = Fragment(comb, {"i": isync, "o": osync}, specials=disable_srl)
v = verilog.convert(f, {i, o})
print(v)
