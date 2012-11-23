from migen.fhdl.structure import *
from migen.fhdl import verilog

mem = Memory(32, 100, init=[5, 18, 32])
p1 = mem.get_port(write_capable=True, we_granularity=8)
p2 = mem.get_port(has_re=True, clock_domain="rd")

f = Fragment(memories=[mem])
v = verilog.convert(f, ios={p1.adr, p1.dat_r, p1.we, p1.dat_w,
	p2.adr, p2.dat_r, p2.re})
print(v)
