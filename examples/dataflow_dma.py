import networkx as nx

from migen.fhdl import verilog
from migen.flow.ala import *
from migen.flow.network import *
from migen.actorlib import dma_wishbone, control

L = [
	("x", BV(10), 8),
	("y", BV(10), 8),
	("level2", [
		("a", BV(5), 32),
		("b", BV(5), 16)
	])
]

adrgen = control.For(10)
reader = dma_wishbone.Reader(L)

g = nx.MultiDiGraph()
add_connection(g, adrgen, reader)
comp = CompositeActor(g)

frag = comp.get_fragment()
ios = set(reader.bus.signals())
ios.add(comp.busy)
print(verilog.convert(frag, ios=ios))
