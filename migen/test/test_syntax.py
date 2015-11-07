import unittest
import subprocess
import os

from migen import *
from migen.fhdl.verilog import convert


# Create a module with some combinatorial, some sequential, and some simple
# assigns
class SyntaxModule(Module):
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
class SyntaxCase(unittest.TestCase):
    def base_test(self, name, asic_syntax, options=[]):
        filename = "test_module_{}.v".format(name)
        t = SyntaxModule()
        c = convert(t, t.io, name="test_module", asic_syntax=asic_syntax)
        f = open(filename, "w")
        f.write(str(c))
        f.close()
        subprocess.check_call("verilator --lint-only " + " ".join(options) + " " + filename,
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, shell=True)
        os.unlink(filename)

    # XXX for now desactivate, travis-ci's Verilator seems to behave differently
    # XXX upgrade travis-ci's Verilator?
    #def test_generic_syntax(self):
    #    options = [
    #        "-Wno-WIDTH",
    #        "-Wno-COMBDLY",
    #        "-Wno-INITIALDLY"
    #    ]
    #    self.base_test("generic", False, options)

    def test_asic_syntax(self):
        options = [
            "-Wno-WIDTH",  # XXX should we improve ASIC backend to remove this?
        ]
        self.base_test("asic", True, options)
