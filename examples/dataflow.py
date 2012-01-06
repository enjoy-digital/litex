import networkx as nx

from migen.fhdl import verilog 
from migen.flow.ala import *
from migen.flow.plumbing import *
from migen.flow.network import *

def get_actor_fragments(*actors):
	return sum([a.get_control_fragment() + a.get_process_fragment() for a in actors], Fragment())

act = Adder(32)
comb = Combinator(act.operands.template(), ["a"], ["b"])
outbuf = Buffer(act.result.template())

g = nx.MultiDiGraph()
g.add_nodes_from([act, comb, outbuf])
add_connection(g, comb, act)
add_connection(g, act, outbuf)
c = CompositeActor(g)

frag = c.get_control_fragment() + c.get_process_fragment()

print(verilog.convert(frag))
