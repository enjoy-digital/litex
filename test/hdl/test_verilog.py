import re
import unittest

from migen import *

from litex.gen.fhdl.verilog import VerilogTime, convert


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


class _DisplayTime(Module):
    def __init__(self):
        self.clock_domains.cd_sys = ClockDomain()
        self.clk   = Signal(name="clk")
        self.value = Signal(8, name="value")

        self.comb += self.cd_sys.clk.eq(self.clk)
        self.sync += Display("time=%t value=%d", VerilogTime(), self.value)


class _Constants(Module):
    def __init__(self):
        self.count   = Signal(8,  name="count")
        self.address = Signal(32, name="address")
        self.mask    = Signal(16, name="mask")

        self.comb += [
            self.count.eq(Constant(42, 8)),
            self.address.eq(Constant(0x80000000, 32)),
            self.mask.eq(Constant(0xffff, 16)),
        ]


class TestVerilog(unittest.TestCase):
    def test_sliced_comb_target_is_declared_as_reg(self):
        dut = _SlicedCombTarget()
        v = convert(dut, ios={dut.flag, dut.count, dut.o}, name="top").main_source

        self.assertRegex(v, r"reg\s+\[29:0\]\s+status")
        self.assertNotRegex(v, r"wire\s+\[29:0\]\s+status")
        self.assertIn("always @(*) begin", v)
        self.assertIn("status[0] = flag;", v)
        self.assertIn("status[12:8] = count;", v)

    def test_sync_output_port_is_declared_as_reg(self):
        dut = _SyncOutput()
        v = convert(dut, ios={dut.clk, dut.i, dut.o}, name="top").main_source

        self.assertRegex(v, r"output reg\s+o")
        self.assertNotRegex(v, r"output wire\s+o")
        self.assertIn("always @(posedge sys_clk) begin", v)
        self.assertIn("o <= i;", v)

    def test_display_can_emit_verilog_time(self):
        dut = _DisplayTime()
        v = convert(dut, ios={dut.clk, dut.value}, name="top").main_source

        self.assertIn('$display("time=%t value=%d", $time, value);', v)
        self.assertNotIn('"$time"', v)

    def test_constants_use_readable_bases(self):
        dut = _Constants()
        v = convert(dut, ios={dut.count, dut.address, dut.mask}, name="top").main_source

        self.assertIn("assign count = 8'd42;", v)
        self.assertIn("assign address = 32'h80000000;", v)
        self.assertIn("assign mask = 16'hffff;", v)


if __name__ == "__main__":
    unittest.main()
