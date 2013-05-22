from migen.fhdl.std import *
from migen.fhdl import verilog
from migen.genlib.fsm import FSM

class Example(Module):
	def __init__(self):
		self.s = Signal()
		myfsm = FSM("FOO", "BAR")
		self.submodules += myfsm
		myfsm.act(myfsm.FOO, self.s.eq(1), myfsm.next_state(myfsm.BAR))
		myfsm.act(myfsm.BAR, self.s.eq(0), myfsm.next_state(myfsm.FOO))

example = Example()
print(verilog.convert(example, {example.s}))
