from random import Random

from migen import *
from migen.genlib.cdc import GrayCounter


def tb(dut):
    prng = Random(7345)
    for i in range(35):
        print("{0:0{1}b} CE={2} bin={3}".format((yield dut.q),
            len(dut.q), (yield dut.ce), (yield dut.q_binary)))
        yield dut.ce.eq(prng.getrandbits(1))
        yield


if __name__ == "__main__":
    dut = GrayCounter(3)
    run_simulation(dut, tb(dut), vcd_name="graycounter.vcd")
