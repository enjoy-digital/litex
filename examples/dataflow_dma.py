import sys
import networkx as nx

from migen.fhdl import verilog
from migen.flow.ala import *
from migen.flow.network import *
from migen.actorlib import dma_wishbone

L = [
	("x", BV(10), 8),
	("y", BV(10), 8),
	("level2", [
		("a", BV(5), 32),
		("b", BV(5), 16)
	])
]

reader = dma_wishbone.Reader(L)
frag = reader.get_fragment()
print(verilog.convert(frag, ios=set(reader.bus.signals())))
