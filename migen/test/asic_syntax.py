import unittest
import subprocess
import os

from migen.fhdl.std import *
from migen.fhdl.verilog import convert


# Create a module with some combinatorial, some sequential, and some simple assigns
class ThingBlock(Module):
    def __init__(self):
        x = [Signal(8) for y in range(10)]
        y = [Signal(8) for z in range(10)]
        en = Signal()
        a = Signal()
        b = Signal()
        z = Signal()
        as_src = Signal(16);
        as_tgt1 = Signal(16);
        as_tgt2 = Signal(16);
        self.io = {a, b, z, en, as_src, as_tgt1, as_tgt2}

        self.comb += If(a, z.eq(b))
        self.comb += as_tgt1.eq(as_src)
        self.comb += as_tgt2.eq(100)
        for xi in x:
            self.io.add(xi)
        for xi in range(1, len(x)):
            self.comb += If(en, y[xi].eq(x[xi-1])).Else(y[xi].eq(x[xi]))
            self.sync += x[xi].eq(y[xi])


# Create unit test to build module, run Verilator and check for errors
class TestThingBlock(unittest.TestCase):
    def test_mode_true(self):
        filename = "test_module_true.v"
        t = ThingBlock()
        with open(filename, "w") as fh:
            fh.write("/* verilator lint_off WIDTH */\n")
            fh.write(str(convert(t, t.io, name="test_module",
                                 asic_syntax=True)))

        subprocess.check_call("verilator --lint-only " + filename,
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, shell=True)
        os.unlink(filename)

    def test_mode_false(self):
        filename = "test_module_false.v"
        t = ThingBlock()
        with open(filename, "w") as fh:
            fh.write(str(convert(t, t.io, name="test_module")))

        with self.assertRaises(subprocess.CalledProcessError):
            subprocess.check_call("verilator --lint-only " + filename,
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, shell=True)
        os.unlink(filename)
