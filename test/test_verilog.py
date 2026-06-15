import re
import unittest

from migen import *

from litex.gen.fhdl.verilog import convert


class _SlicedCombTarget(Module):
    def __init__(self):
        self.flag   = Signal(name="flag")
        self.count  = Signal(5, name="count")
        self.status = Signal(30, name="status")
        self.o      = Signal(name="o")

        self.comb += [
            self.status[0].eq(self.flag),
            self.status[8:13].eq(self.count),
            self.o.eq(self.status[0]),
        ]


class _SyncOutput(Module):
    def __init__(self):
        self.clock_domains.cd_sys = ClockDomain()
        self.clk = Signal(name="clk")
        self.i   = Signal(name="i")
        self.o   = Signal(name="o", reset=1)

        self.comb += self.cd_sys.clk.eq(self.clk)
        self.sync += self.o.eq(self.i)


class TestVerilog(unittest.TestCase):
    def test_sliced_comb_target_is_declared_as_reg(self):
        dut = _SlicedCombTarget()
        v = convert(dut, ios={dut.flag, dut.count, dut.o}, name="top").main_source

        self.assertRegex(v, r"reg\s+\[29:0\]\s+status")
        self.assertNotRegex(v, r"wire\s+\[29:0\]\s+status")
        self.assertIn("always @(*) begin", v)
        self.assertIn("status[0] <= flag;", v)
        self.assertIn("status[12:8] <= count;", v)

    def test_sync_output_port_is_declared_as_reg(self):
        dut = _SyncOutput()
        v = convert(dut, ios={dut.clk, dut.i, dut.o}, name="top").main_source

        self.assertRegex(v, r"output reg\s+o")
        self.assertNotRegex(v, r"output wire\s+o")
        self.assertIn("always @(posedge sys_clk) begin", v)
        self.assertIn("o <= i;", v)


if __name__ == "__main__":
    unittest.main()
