import unittest
import random

from litex.gen import *
from litex.gen.genlib.cdc import Gearbox

# TODO:
# connect two gearbox together:
# first gearbox: iwidth > owidth
# second gearbox: iwidth < owidth
# use 2 clock domains
# compare input data to output data, should be similar
# various datawidth/clock ratios


def data_generator(dut):
    for i in range(256):
        yield dut.i.eq(i)
        yield
    yield

@passive
def data_checker(dut):
    while True:
        #print((yield dut.o))
        yield


class GearboxDUT(Module):
    def __init__(self):
        self.submodules.gearbox_down = Gearbox(10, "user", 8, "gearbox")
        self.submodules.gearbox_up = Gearbox(8, "gearbox", 10, "user")
        self.comb += self.gearbox_up.i.eq(self.gearbox_down.o)
        self.i, self.o = self.gearbox_down.i, self.gearbox_up.o


class TestGearbox(unittest.TestCase):
    def test_gearbox(self):
        dut = GearboxDUT()
        generators = {"user": [data_generator(dut), data_checker(dut)]}
        clocks = {"user": 12.5, "gearbox": 10}
        run_simulation(dut, generators, clocks, vcd_name="sim.vcd")
        self.assertEqual(0, 0)
