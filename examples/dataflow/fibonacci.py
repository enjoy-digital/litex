import sys

from migen.flow.ala import *
from migen.flow.network import *
from migen.flow import plumbing
from migen.actorlib.sim import *
from migen.sim.generic import Simulator
from migen.sim.icarus import Runner

# Pushes a "1" token and then becomes transparent.
class Init(Actor):
	def __init__(self, nbits):
		super().__init__(
			("in", Sink, [("d", BV(nbits))]),
			("out", Source, [("d", BV(nbits))]))
	
	def get_fragment(self):
		done = Signal()
		comb = [
			self.busy.eq(~done),
			If(done,
				self.endpoints["in"].ack.eq(self.endpoints["out"].ack),
				self.endpoints["out"].stb.eq(self.endpoints["in"].stb),
				self.endpoints["out"].token.d.eq(self.endpoints["in"].token.d)
			).Else(
				self.endpoints["in"].ack.eq(0),
				self.endpoints["out"].stb.eq(1),
				self.endpoints["out"].token.d.eq(1)
			)
		]
		sync = [
			If(self.endpoints["out"].ack, done.eq(1))
		]
		return Fragment(comb, sync)

class Dumper(SimActor):
	def __init__(self, nbits):
		def dumper_gen():
			while True:
				t = Token("result")
				yield t
				print(t.value["r"])
		super().__init__(dumper_gen(),
			("result", Sink, [("r", BV(nbits))]))

def main():
	nbits = 32
	
	# See:
	# http://www.csse.monash.edu.au/~damian/Idioms/Topics/12.1.DataFlow/html/text.html
	g = DataFlowGraph()
	
	adder = ActorNode(Add(BV(nbits)))
	bufadd = ActorNode(plumbing.Buffer) # TODO FIXME: deadlocks without this buffer
	init1 = ActorNode(Init(nbits))
	buf1 = ActorNode(plumbing.Buffer)
	init2 = ActorNode(Init(nbits))
	buf2 = ActorNode(plumbing.Buffer)
	
	g.add_connection(adder, bufadd)
	g.add_connection(bufadd, init1)
	g.add_connection(init1, buf1)
	g.add_connection(buf1, adder, sink_subr="a")
	g.add_connection(buf1, init2)
	g.add_connection(init2, buf2)
	g.add_connection(buf2, adder, sink_subr="b")
	
	g.add_connection(bufadd, ActorNode(Dumper(nbits)))
	
	c = CompositeActor(g)
	fragment = c.get_fragment()
	sim = Simulator(fragment, Runner())
	sim.run(100)
	
main()
