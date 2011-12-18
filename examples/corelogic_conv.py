from migen.fhdl import verilog
from migen.corelogic import roundrobin, divider

r = roundrobin.Inst(5)
d = divider.Inst(16)
frag = r.get_fragment() + d.get_fragment()
o = verilog.Convert(frag, {r.request, r.grant, d.ready_o, d.quotient_o, d.remainder_o, d.start_i, d.dividend_i, d.divisor_i})
print(o)
