import sys

import matplotlib.pyplot as plt
import networkx as nx

from migen.flow.ala import *
from migen.flow.network import *
from migen.flow.composer import *
from migen.actorlib.sim import *
from migen.sim.generic import Simulator
from migen.sim.icarus import Runner

class NumberGen(SimActor):
	def __init__(self):
		self.bv_r = BV(16)
		def number_gen():
			for i in range(10):
				yield Token("result", {"r": i})
		super().__init__(number_gen(),
			("result", Source, [("r", self.bv_r)]))

class Dumper(SimActor):
	def __init__(self):
		def dumper_gen():
			while True:
				t = Token("result")
				yield t
				print("Received: " + str(t.value["r"]))
		super().__init__(dumper_gen(),
			("result", Sink, [("r", BV(32))]))

def main():
	# Create graph
	g = DataFlowGraph()
	a1 = ComposableSource(g, NumberGen())
	a2 = ComposableSource(g, NumberGen())
	a3 = ComposableSource(g, NumberGen())
	c3 = (a1 + a2)*a3
	g.add_connection(c3.actor_node, Dumper())

	a1.actor_node.actor.name = "gen1"
	a2.actor_node.actor.name = "gen2"
	a3.actor_node.actor.name = "gen3"
	c3.actor_node.name = "result"
	
	# Elaborate
	draw = len(sys.argv) > 1 and sys.argv[1] == "draw"
	print("is_abstract before elaboration: " + str(g.is_abstract()))
	if draw:
		nx.draw(g)
		plt.show()
	g.elaborate()
	print("is_abstract after elaboration : " + str(g.is_abstract()))
	if draw:
		nx.draw(g)
		plt.show()

	# Simulate
	c = CompositeActor(g)
	fragment = c.get_fragment()
	sim = Simulator(fragment, Runner())
	sim.run(100)

main()
