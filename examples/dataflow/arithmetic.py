import sys

import matplotlib.pyplot as plt
import networkx as nx

from migen.flow.network import *
from migen.actorlib.ala import *
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
				print(t.value["r"])
		super().__init__(dumper_gen(),
			("result", Sink, [("r", BV(32))]))

def draw(g):
	if len(sys.argv) > 1 and sys.argv[1] == "draw":
		nx.draw_spectral(g)
		plt.show()

def main():
	# Create graph
	g = DataFlowGraph()
	gen1 = ComposableNode(g, NumberGen())
	gen2 = ComposableNode(g, NumberGen())
	
	ps = gen1 + gen2
	result = ps*gen1 + ps*gen2
	
	g.add_connection(result, ActorNode(Dumper()))

	gen1.actor.name = "gen1"
	gen2.actor.name = "gen2"
	result.name = "result"
	
	# Elaborate
	print("is_abstract before elaboration: " + str(g.is_abstract()))
	draw(g)
	g.elaborate()
	print("is_abstract after elaboration : " + str(g.is_abstract()))
	draw(g)

	# Simulate
	c = CompositeActor(g)
	fragment = c.get_fragment()
	sim = Simulator(fragment, Runner())
	sim.run(100)

main()
