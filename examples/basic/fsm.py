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
		self.entering_foo = myfsm.entering("FOO")
		self.leaving_bar = myfsm.leaving("BAR")

example = Example()
print(verilog.convert(example, {example.s, example.entering_foo, example.leaving_bar}))
