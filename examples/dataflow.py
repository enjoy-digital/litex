import sys

from migen.fhdl import verilog
from migen.flow.ala import *
from migen.flow.network import *
from migen.flow.composer import *

g = DataFlowGraph()
a1 = make_composable(g, Add(BV(16)))
a2 = make_composable(g, Add(BV(16)))
a3 = make_composable(g, Add(BV(16)))
c3 = (a1 + a2)*a3
c = CompositeActor(g)

frag = c.get_fragment()

print(verilog.convert(frag))

if len(sys.argv) > 1 and sys.argv[1] == "draw":
	import matplotlib.pyplot as plt
	import networkx as nx
	nx.draw(g)
	plt.show()
