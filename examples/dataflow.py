import networkx as nx

from migen.fhdl import verilog 
from migen.flow.ala import *
from migen.flow.network import *
from migen.flow.composer import *

g = nx.MultiDiGraph()
a1 = make_composable(g, Add(BV(16)))
a2 = make_composable(g, Add(BV(16)))
a3 = make_composable(g, Add(BV(16)))
c3 = (a1 + a2)*a3
print(c3)
c = CompositeActor(g)

frag = c.get_control_fragment() + c.get_process_fragment()

print(verilog.convert(frag))
