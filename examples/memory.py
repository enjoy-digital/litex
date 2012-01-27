from migen.fhdl.structure import *
from migen.fhdl import verilog

d = 100
d_b = bits_for(d-1)
w = 32

a1 = Signal(BV(d_b))
d1 = Signal(BV(w))
we1 = Signal(BV(4))
dw1 = Signal(BV(w))
p1 = MemoryPort(a1, d1, we1, dw1, we_granularity=8, mode=WRITE_FIRST)

a2 = Signal(BV(d_b))
d2 = Signal(BV(w))
p2 = MemoryPort(a2, d2)

mem = Memory(w, d, p1, p2, init=[5, 18, 32])
f = Fragment(memories=[mem])
v = verilog.convert(f, ios={a1, d1, we1, dw1, a2, d2})
print(v)
