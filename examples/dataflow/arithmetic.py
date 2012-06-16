import sys

import matplotlib.pyplot as plt
import networkx as nx

from migen.fhdl import verilog
from migen.flow.ala import *
from migen.flow.network import *
from migen.flow.composer import *

draw = len(sys.argv) > 1 and sys.argv[1] == "draw"

# Create graph
g = DataFlowGraph()
a1 = ComposableSource(g, Add(BV(16)))
a2 = ComposableSource(g, Add(BV(16)))
a3 = ComposableSource(g, Add(BV(16)))
c3 = (a1 + a2)*a3

a1.actor_node.name = "in1"
a2.actor_node.name = "in2"
a3.actor_node.name = "in3"
c3.actor_node.name = "result"

# Elaborate
print("is_abstract before elaboration: " + str(g.is_abstract()))
if draw:
	nx.draw(g)
	plt.show()
g.elaborate()
print("is_abstract after elaboration : " + str(g.is_abstract()))
if draw:
	nx.draw(g)
	plt.show()

# Convert
c = CompositeActor(g)
frag = c.get_fragment()
print(verilog.convert(frag))
