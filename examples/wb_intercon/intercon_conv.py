from migen.fhdl import verilog
from migen.bus import wishbone

m1 = wishbone.Master()
m2 = wishbone.Master()
s1 = wishbone.Slave()
s2 = wishbone.Slave()
wishbonecon0 = wishbone.InterconnectShared(
		[m1, m2],
		[(0, s1), (1, s2)],
		register=True,
		offset=1)

frag = wishbonecon0.get_fragment()
v = verilog.convert(frag, name="intercon", ios={m1.cyc_o, m1.stb_o, m1.we_o, m1.adr_o, m1.sel_o, m1.dat_o, m1.dat_i, m1.ack_i,
	m2.cyc_o, m2.stb_o, m2.we_o, m2.adr_o, m2.sel_o, m2.dat_o, m2.dat_i, m2.ack_i,
	s1.cyc_i, s1.stb_i, s1.we_i, s1.adr_i, s1.sel_i, s1.dat_i, s1.dat_o, s1.ack_o,
	s2.cyc_i, s2.stb_i, s2.we_i, s2.adr_i, s2.sel_i, s2.dat_i, s2.dat_o, s2.ack_o})
print(v)
