from migen.fhdl import verilog 
from migen.flow.ala import *
from migen.flow.plumbing import *

act = Adder(32)
comb = Combinator(act.operands, ["a"], ["b"])
outbuf = Buffer(act.result.template())
frag = get_actor_fragments(act, comb, outbuf)

stb_a = comb.sinks[0].stb
ack_a = comb.sinks[0].ack
stb_b = comb.sinks[1].stb
ack_b = comb.sinks[1].ack
stb_a.name = "stb_a_i"
ack_a.name = "ack_a_o"
stb_b.name = "stb_b_i"
ack_b.name = "stb_b_o"
a = comb.ins[0].a
b = comb.ins[1].b
a.name = "a"
b.name = "b"
print(verilog.convert(frag, ios={stb_a, ack_a, stb_b, ack_b, a, b}))
