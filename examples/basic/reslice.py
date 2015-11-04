from migen import *
from migen.fhdl import verilog


class Example(Module):
    def __init__(self):
        a = Signal(3)
        b = Signal(4)
        c = Signal(5)
        d = Signal(7)
        s1 = c[:3][:2]
        s2 = Cat(a, b)[:6]
        s3 = Cat(s1, s2)[-5:]
        self.comb += s3.eq(0)
        self.comb += d.eq(Cat(d[::-1], Cat(s1[:1], s3[-4:])[:3]))


if __name__ == "__main__":
    print(verilog.convert(Example()))
