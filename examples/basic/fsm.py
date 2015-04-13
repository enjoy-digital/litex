from migen.fhdl.std import *
from migen.fhdl import verilog
from migen.genlib.fsm import FSM, NextState, NextValue


class Example(Module):
    def __init__(self):
        self.s = Signal()
        self.counter = Signal(8)

        myfsm = FSM()
        self.submodules += myfsm

        myfsm.act("FOO",
            self.s.eq(1),
            NextState("BAR")
        )
        myfsm.act("BAR",
            self.s.eq(0),
            NextValue(self.counter, self.counter + 1),
            NextState("FOO")
        )

        self.be = myfsm.before_entering("FOO")
        self.ae = myfsm.after_entering("FOO")
        self.bl = myfsm.before_leaving("FOO")
        self.al = myfsm.after_leaving("FOO")

example = Example()
print(verilog.convert(example, {example.s, example.counter, example.be, example.ae, example.bl, example.al}))
