import re
import random
import unittest

from migen import *
from migen.fhdl.tools import group_by_targets
from migen.fhdl.namer import build_namespace

from litex.gen.fhdl.verilog import VerilogTime, convert
from litex.gen.fhdl.verilog import _group_by_targets, _topological_sort_targets


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


class _ForwardCombReference(Module):
    def __init__(self):
        self.sel = Signal(name="sel")
        self.a   = Signal(name="a")
        self.b   = Signal(name="b")

        self.comb += If(self.sel,
            self.a.eq(self.b),
            self.b.eq(1),
        )


class _OrderedCombReference(Module):
    def __init__(self):
        self.sel = Signal(name="sel")
        self.a   = Signal(name="a")
        self.b   = Signal(name="b")

        self.comb += If(self.sel,
            self.b.eq(1),
            self.a.eq(self.b),
        )


class _CombCycle(Module):
    def __init__(self):
        self.a = Signal(name="a")
        self.b = Signal(name="b")

        self.comb += [
            self.a.eq(self.b),
            self.b.eq(self.a),
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

    def test_forward_comb_reference_is_dependency_ordered(self):
        dut = _ForwardCombReference()
        v = convert(dut, ios={dut.sel, dut.a, dut.b}, name="top").main_source

        self.assertIn("a = 1'd0;", v)
        self.assertIn("b = 1'd0;", v)
        self.assertIn("b = 1'd1;", v)
        self.assertIn("a = b;", v)
        self.assertLess(v.index("b = 1'd1;"), v.index("a = b;"))
        self.assertNotIn("a <= b;", v)

    def test_ordered_comb_reference_keeps_blocking_assignments(self):
        dut = _OrderedCombReference()
        v = convert(dut, ios={dut.sel, dut.a, dut.b}, name="top").main_source

        self.assertIn("a = 1'd0;", v)
        self.assertIn("b = 1'd0;", v)
        self.assertIn("b = 1'd1;", v)
        self.assertIn("a = b;", v)
        self.assertNotIn("a <= b;", v)

    def test_comb_cycle_can_warn(self):
        dut = _CombCycle()
        with self.assertWarnsRegex(RuntimeWarning, "a -> b -> a"):
            convert(dut, ios={dut.a, dut.b}, name="top", comb_cycle_policy="warn")

    def test_comb_cycle_can_error(self):
        dut = _CombCycle()
        with self.assertRaisesRegex(ValueError, "a -> b -> a"):
            convert(dut, ios={dut.a, dut.b}, name="top", comb_cycle_policy="error")

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

    def test_group_by_targets_matches_migen(self):
        # Same groups (targets/statements) in the same order as Migen's group_by_targets.
        prng = random.Random(42)
        sigs = [Signal(name=f"s{i}") for i in range(32)]
        statements = []
        for i in range(200):
            a, b, c = prng.sample(sigs, 3)
            statements.append(prng.choice([
                a.eq(b),
                If(c, a.eq(b)),
                If(c, a.eq(1), b.eq(0)),
                [a.eq(c), b.eq(c)],
            ]))
            sigs.append(Signal(name=f"s{len(sigs)}")) # Keep some groups disjoint.
        expected = group_by_targets(statements)
        actual   = _group_by_targets(statements)
        self.assertEqual(len(actual), len(expected))
        for (actual_targets, actual_stmts), (expected_targets, expected_stmts) in zip(actual, expected):
            self.assertEqual(actual_targets, expected_targets)
            self.assertEqual([id(s) for s in actual_stmts], [id(s) for s in expected_stmts])

    def test_topological_sort_targets(self):
        def reference_sort(targets, deps, ns):
            remaining = set(targets)
            ordered   = []
            while remaining:
                ready = [t for t in remaining if deps.get(t, set()).isdisjoint(remaining)]
                if not ready:
                    return None
                ready = sorted(ready, key=lambda x: ns.get_name(x))
                ordered.append(ready[0])
                remaining.remove(ready[0])
            return ordered

        prng = random.Random(42)
        sigs = [Signal(name=f"t{i}") for i in range(64)]
        ns   = build_namespace(sigs)
        # Random DAG (deps only on lower indexes): same order as the reference.
        deps = {s: set(prng.sample(sigs[:i], min(i, prng.randrange(4)))) for i, s in enumerate(sigs)}
        self.assertEqual(_topological_sort_targets(sigs, deps, ns), reference_sort(sigs, deps, ns))
        # Cycle: None.
        deps[sigs[0]] = {sigs[-1]}
        deps[sigs[-1]] |= {sigs[0]}
        self.assertIsNone(_topological_sort_targets(sigs, deps, ns))


if __name__ == "__main__":
    unittest.main()
