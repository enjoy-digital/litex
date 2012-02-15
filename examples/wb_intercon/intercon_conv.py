from migen.fhdl import verilog
from migen.bus import wishbone

m1 = wishbone.Interface()
m2 = wishbone.Interface()
s1 = wishbone.Interface()
s2 = wishbone.Interface()
wishbonecon0 = wishbone.InterconnectShared(
		[m1, m2],
		[(0, s1), (1, s2)],
		register=True,
		offset=1)

frag = wishbonecon0.get_fragment()
v = verilog.convert(frag, name="intercon", ios={m1.cyc, m1.stb, m1.we, m1.adr, m1.sel, m1.dat_w, m1.dat_r, m1.ack,
	m2.cyc, m2.stb, m2.we, m2.adr, m2.sel, m2.dat_r, m2.dat_w, m2.ack,
	s1.cyc, s1.stb, s1.we, s1.adr, s1.sel, s1.dat_r, s1.dat_w, s1.ack,
	s2.cyc, s2.stb, s2.we, s2.adr, s2.sel, s2.dat_r, s2.dat_w, s2.ack})
print(v)
