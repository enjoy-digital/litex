from migen import *
from migen.fhdl import verilog


L = [
    ("position", [
            ("x", 10, DIR_M_TO_S),
            ("y", 10, DIR_M_TO_S),
    ]),
    ("color", 32, DIR_M_TO_S),
    ("stb", 1, DIR_M_TO_S),
    ("ack", 1, DIR_S_TO_M)
]


class Test(Module):
    def __init__(self):
        master = Record(L)
        slave = Record(L)
        self.comb += master.connect(slave)


if __name__ == "__main__":
    print(verilog.convert(Test()))
    print(layout_len(L))
    print(layout_partial(L, "position/x", "color"))
