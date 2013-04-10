from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.flow.transactions import *
from migen.flow.network import *
from migen.actorlib.sim import *
from migen.sim.generic import Simulator

def source_gen():
	for i in range(10):
		print("Sending:  " + str(i))
		yield Token("source", {"value": i})

class SimSource(SimActor):
	def __init__(self):
		self.source = Source([("value", 32)])
		SimActor.__init__(self, source_gen())

def sink_gen():
	while True:
		t = Token("sink")
		yield t
		print("Received: " + str(t.value["value"]))

class SimSink(SimActor):
	def __init__(self):
		self.sink = Sink([("value", 32)])
		SimActor.__init__(self, sink_gen())

class TB(Module):
	def __init__(self):
		self.source = SimSource()
		self.sink = SimSink()
		g = DataFlowGraph()
		g.add_connection(self.source, self.sink)
		self.submodules.comp = CompositeActor(g)

	def do_simulation(self, s):
		s.interrupt = self.source.token_exchanger.done

Simulator(TB()).run()
