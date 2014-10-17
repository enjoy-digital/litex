from migen.flow.network import *
from migen.flow.transactions import *
from migen.actorlib.sim import *
from migen.pytholite.compiler import Pytholite
from migen.sim.generic import run_simulation
from migen.fhdl import verilog

layout = [("r", 32)]

def number_gen(n):
	for i in range(n):
		yield Token("result", {"r": i})

class SimNumberGen(SimActor):
	def __init__(self):
		self.result = Source(layout)
		SimActor.__init__(self, number_gen(5))

def run_ng_sim(ng):
	g = DataFlowGraph()
	d = Dumper(layout)
	g.add_connection(ng, d)

	c = CompositeActor(g)
	run_simulation(c, ncycles=20)

def make_ng_pytholite():
	ng_pytholite = Pytholite(number_gen, 5)
	ng_pytholite.result = Source(layout)
	ng_pytholite.finalize()
	return ng_pytholite

def main():
	print("Simulating native Python:")
	ng_native = SimNumberGen()
	run_ng_sim(ng_native)

	print("Simulating Pytholite:")
	ng_pytholite = make_ng_pytholite()
	run_ng_sim(ng_pytholite)

	print("Converting Pytholite to Verilog:")
	ng_pytholite = make_ng_pytholite()
	print(verilog.convert(ng_pytholite))

main()
