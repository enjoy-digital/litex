from migen.fhdl.std import *
from migen.fhdl import verilog
from migen.genlib.fsm import FSM, NextState

class Example(Module):
	def __init__(self):
		self.s = Signal()
		myfsm = FSM()
		self.submodules += myfsm
		myfsm.act("FOO", self.s.eq(1), NextState("BAR"))
		myfsm.act("BAR", self.s.eq(0), NextState("FOO"))

example = Example()
print(verilog.convert(example, {example.s}))
