#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Expressions semantics of the Verilog generation and of the simulator (see verilog_semantics.py):
regression cases found in designs and random expressions in the Verilog contexts."""

import random
import unittest
from functools import reduce
from operator import add

from migen import *

from test.hdl.verilog_semantics import *

from litex.gen.sim import run_simulation

# Regression Cases ---------------------------------------------------------------------------------

def regression_cases():
    """(name, inputs layouts, function of the inputs returning (expression, output layout)).

    Expressions whose generated Verilog (or simulation) did not match the simulator semantics."""
    return [
        # Sum of 1-bit values compared to a constant (popcount): evaluated on 1 bit in Verilog.
        ("popcount_compare", [1, 1, 1], lambda a, b, c: (reduce(add, [a, b, c]) > 1, 1)),
        # Variable shift by a byte offset (8*n): shift amount truncated in Verilog.
        ("shift_byte_offset", [32, 2], lambda x, n: (x >> (8*n), 8)),
        # Counter increment by an inverted 1-bit event: ~ widened (all ones) in Verilog/simulator.
        ("counter_inverted_event", [8, 1, 1], lambda c, a, b: (c + (~a & ~b), 8)),
        # Inverted 1-bit value as a Mux condition: always true in the simulator.
        ("mux_inverted_condition", [1, 4, 4], lambda s, a, b: (Mux(~s, a, b), 4)),
        # Inverted unsigned value assigned to a wider target: extension bits inverted in Verilog.
        ("inverted_wider_target", [3], lambda a: (~a, 6)),
        # Signed positive constant: printed unsigned (expression turned unsigned) in Verilog.
        ("signed_positive_constant", [(2, True)], lambda a: ((~a) > Constant(7, (4, True)), 1)),
        # 1-bit slice of a 1-bit signed Signal: printed as the (signed) Signal in Verilog.
        ("signed_1bit_slice", [(1, True), 3], lambda a, b: ((b ^ a[0:1]) == 0, 1)),
        # Signed x signed product: one more bit than the Migen width rule.
        ("signed_product", [(2, True), (2, True)], lambda a, b: ((a*b) > 3, 1)),
        # Carry of a sum in a concatenation: truncated in Verilog.
        ("sum_in_cat", [4, 4, 2], lambda a, b, c: (Cat(a + b, c), 7)),
        # Unsigned subtraction compared: exact (negative) value.
        ("unsigned_subtraction_compare", [4, 4], lambda a, b: ((a - b) < 0, 1)),
        # Right shift of a sum (average): carry truncated in Verilog.
        ("average", [4, 4], lambda a, b: ((a + b) >> 1, 4)),
    ]

class RegressionModule(Module):
    def __init__(self, inputs, make):
        self.inputs  = [Signal(layout, name=f"i{n}") for n, layout in enumerate(inputs)]
        expr, layout = make(*self.inputs)
        o = Signal(layout, name="o0")
        self.outputs = [o]
        self.expr    = expr
        self.refs    = [(o, lambda env: truncate(ref_eval(expr, env), len(o), o.signed))]
        self.comb += o.eq(expr)

def all_vectors(module, rng, n=128):
    vectors = random_vectors(module, rng, n)
    if sum(len(s) for s in module.inputs) <= 8:
        # Exhaustive.
        vectors = [[]]
        for s in module.inputs:
            vectors = [v + [truncate(x, len(s), s.signed)] for v in vectors for x in range(2**len(s))]
    return vectors

def module_mismatches(module, vectors, results):
    mismatches = []
    for vector, result in zip(vectors, results):
        env = dict(zip(module.inputs, vector))
        for (o, ref), got in zip(module.refs, result):
            expected = ref(env) & ((1 << len(o)) - 1)
            if got != expected:
                mismatches.append((vector, expected, got))
    return mismatches

def simulate(module, vectors):
    results = []
    def generator():
        for vector in vectors:
            for s, v in zip(module.inputs, vector):
                yield s.eq(v)
            yield
            result = []
            for o in module.outputs:
                result.append((yield o) & ((1 << len(o)) - 1))
            results.append(result)
    run_simulation(module, generator())
    return results

# Tests --------------------------------------------------------------------------------------------

class TestVerilogSemantics(unittest.TestCase):
    def test_regressions_simulator(self):
        for name, inputs, make in regression_cases():
            with self.subTest(name):
                m = RegressionModule(inputs, make)
                vectors = all_vectors(m, random.Random(0))
                self.assertEqual(module_mismatches(m, vectors, simulate(m, vectors))[:4], [])

    @unittest.skipUnless(verilator_available(), "verilator not found")
    def test_regressions_verilog(self):
        for name, inputs, make in regression_cases():
            with self.subTest(name):
                m = RegressionModule(inputs, make)
                vectors = all_vectors(m, random.Random(0))
                self.assertEqual(module_mismatches(m, vectors, verilator_eval(m, vectors))[:4], [])

    def test_fuzz_simulator(self):
        for seed in range(8):
            with self.subTest(seed=seed):
                kwargs = dict(max_depth=4, max_width=8) if seed % 2 else {}
                m, mismatches = check_simulator(seed, **kwargs)
                self.assertEqual([(n, m.exprs[n][1]) for n, *_ in mismatches][:4], [])

    @unittest.skipUnless(verilator_available(), "verilator not found")
    def test_fuzz_verilog(self):
        for seed in range(8):
            with self.subTest(seed=seed):
                kwargs = dict(max_depth=4, max_width=8) if seed % 2 else {}
                m, mismatches = check_verilog(seed, **kwargs)
                self.assertEqual([(n, m.exprs[n][1]) for n, *_ in mismatches][:4], [])

if __name__ == "__main__":
    unittest.main()
