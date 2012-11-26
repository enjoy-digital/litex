from migen.fhdl.structure import *
from migen.fhdl import verilog

dx = 5
dy = 5

x = Signal(BV(bits_for(dx-1)))
y = Signal(BV(bits_for(dy-1)))
out = Signal()

my_2d_array = Array(Array(Signal() for a in range(dx)) for b in range(dy))
comb = [
	out.eq(my_2d_array[x][y])
]

we = Signal()
inp = Signal()
sync = [
	If(we,
		my_2d_array[x][y].eq(inp)
	)
]

f = Fragment(comb, sync)
print(verilog.convert(f))
