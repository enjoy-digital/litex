from migen import *
from migen.fhdl import verilog

from functools import reduce
from operator import or_


def gen_list(n):
    s = [Signal() for i in range(n)]
    return s


def gen_2list(n):
    s = [Signal(2) for i in range(n)]
    return s


class Foo:
    def __init__(self):
        la = gen_list(3)
        lb = gen_2list(2)
        self.sigs = la + lb


class Bar:
    def __init__(self):
        self.sigs = gen_list(2)


class Example(Module):
    def __init__(self):
        a = [Bar() for x in range(3)]
        b = [Foo() for x in range(3)]
        c = b
        b = [Bar() for x in range(2)]

        output = Signal()
        allsigs = []
        for lst in [a, b, c]:
            for obj in lst:
                allsigs.extend(obj.sigs)
        self.comb += output.eq(reduce(or_, allsigs))

print(verilog.convert(Example()))
