from migen import *
from migen.fhdl import verilog

class Example(Module):
    def __init__(self):
        self.s = Signal()
        self.counter = Signal(8)
        x = Array(Signal(name="a") for i in range(7))

        myfsm = FSM()
        self.submodules += myfsm

        myfsm.act("FOO",
            self.s.eq(1),
            NextState("BAR")
        )
        myfsm.act("BAR",
            self.s.eq(0),
            NextValue(self.counter, self.counter + 1),
            NextValue(x[self.counter], 89),
            NextState("FOO")
        )

        self.be = myfsm.before_entering("FOO")
        self.ae = myfsm.after_entering("FOO")
        self.bl = myfsm.before_leaving("FOO")
        self.al = myfsm.after_leaving("FOO")

if __name__ == "__main__":
    example = Example()
    print(verilog.convert(example, {example.s, example.counter, example.be, example.ae, example.bl, example.al}))
