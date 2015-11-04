from migen import *
from migen.fhdl import verilog


class Example(Module):
    def __init__(self, n=6):
        self.pad = Signal(n)
        self.t = TSTriple(n)
        self.specials += self.t.get_tristate(self.pad)

if __name__ == "__main__":
    e = Example()
    print(verilog.convert(e, ios={e.pad, e.t.o, e.t.oe, e.t.i}))
