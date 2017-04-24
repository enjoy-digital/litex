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

def source_generator(dut):
    yield


def sink_generator(duc):
    yield


class GearboxDUT(Module):
    def __init__(self):
        self.submodules.gearbox_down = Gearbox(10, "slow", 8, "fast")
        self.submodules.gearbox_up = Gearbox(8, "fast", 10, "slow")
        self.comb += self.gearbox_up.i.eq(self.gearbox_down.o)
        self.i, self.o = self.gearbox_down.i, self.gearbox_up.o


class TestGearbox(unittest.TestCase):
    def test_gearbox(self):
        self.assertEqual(0, 0)
