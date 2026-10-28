#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Expressions semantics checks of the Verilog generation (and of the simulator).

Reference semantics (ref_eval): the simulator ones, exact integer arithmetic (no truncation inside
the expressions, values truncated to the target width on assignment), except the bitwise inversion
of an unsigned value which has the width of its operand (Migen width rule: ~ on a 1-bit unsigned
Signal is 0 or 1). Cat/Replicate operands are taken on their Migen width (len), If conditions on
len(cond) bits (as the simulator does).

ExpressionFuzzer generates random expressions over random signed/unsigned inputs, used in the
different Verilog contexts (assignment to a narrower/wider target, comparison operands, shift
amounts, Cat operands, Mux/If conditions...). check_verilog() converts the module to Verilog,
evaluates it with Verilator on random input vectors and compares the outputs with ref_eval().
"""

import os
import random
import shutil
import subprocess
import tempfile

from migen import *
from migen.fhdl.structure import _Operator, _Slice
from migen.fhdl.bitcontainer import value_bits_sign

from litex.gen.fhdl.verilog import convert

# Reference Evaluation -----------------------------------------------------------------------------

def truncate(value, nbits, signed):
    value &= (1 << nbits) - 1
    if signed and (value >> (nbits - 1)) & 1:
        value -= (1 << nbits)
    return value

def ref_eval(node, env):
    """Reference value of node (Python int, exact) with the input values of env."""
    if isinstance(node, Constant):
        return node.value
    if isinstance(node, Signal):
        return env[node]
    if isinstance(node, _Operator):
        v = [ref_eval(o, env) for o in node.operands]
        op = node.op
        if op == "~":
            nbits, signed = value_bits_sign(node.operands[0])
            return ~v[0] if signed else (~v[0]) & ((1 << nbits) - 1)
        if op == "-" and len(v) == 1:
            return -v[0]
        if op == "m":
            return v[1] if v[0] else v[2]
        return {
            "+"   : lambda a, b: a + b,
            "-"   : lambda a, b: a - b,
            "*"   : lambda a, b: a * b,
            "<<<" : lambda a, b: a << b,
            ">>>" : lambda a, b: a >> b,
            "&"   : lambda a, b: a & b,
            "|"   : lambda a, b: a | b,
            "^"   : lambda a, b: a ^ b,
            "<"   : lambda a, b: int(a < b),
            "<="  : lambda a, b: int(a <= b),
            ">"   : lambda a, b: int(a > b),
            ">="  : lambda a, b: int(a >= b),
            "=="  : lambda a, b: int(a == b),
            "!="  : lambda a, b: int(a != b),
        }[op](*v)
    if isinstance(node, _Slice):
        return (ref_eval(node.value, env) >> node.start) & ((1 << (node.stop - node.start)) - 1)
    if isinstance(node, Cat):
        r, shift = 0, 0
        for e in node.l:
            r |= (ref_eval(e, env) & ((1 << len(e)) - 1)) << shift
            shift += len(e)
        return r
    if isinstance(node, Replicate):
        v = ref_eval(node.v, env) & ((1 << len(node.v)) - 1)
        return sum(v << (i*len(node.v)) for i in range(node.n))
    raise TypeError(node)

# Expression Fuzzer --------------------------------------------------------------------------------

BINARY_OPS = ["+", "-", "*", "&", "|", "^", "<<", ">>", "<", "<=", ">", ">=", "==", "!="]

class ExpressionFuzzer:
    def __init__(self, seed, n_inputs=6, max_width=6, max_depth=3):
        self.rng       = random.Random(seed)
        self.max_depth = max_depth
        self.inputs    = [Signal((self.rng.randint(1, max_width), self.rng.random() < 0.3), name=f"i{i}")
            for i in range(n_inputs)]

    def leaf(self):
        rng = self.rng
        if rng.random() < 0.8:
            return rng.choice(self.inputs)
        if rng.random() < 0.5:
            return Constant(rng.randint(0, 15))
        return Constant(rng.randint(-8, 7), (4, True))

    def expr(self, depth=0):
        rng = self.rng
        if depth >= self.max_depth or rng.random() < 0.25:
            return self.leaf()
        kind = rng.random()
        a = self.expr(depth + 1)
        if kind < 0.12:
            return ~a
        if kind < 0.16:
            return -a
        if kind < 0.24:
            return Mux(self.expr(depth + 1), a, self.expr(depth + 1))
        if kind < 0.30:
            return Cat(a, self.expr(depth + 1))
        if kind < 0.33:
            return Replicate(a, rng.randint(1, 3))
        if kind < 0.38:
            n = len(a)
            start = rng.randint(0, n - 1)
            return a[start:rng.randint(start + 1, n)]
        op = rng.choice(BINARY_OPS)
        if op in ["<<", ">>"]:
            # Unsigned shift amounts of 1-3 bits (Migen shift results grow with 2**len(amount)).
            b = self.expr(depth + 1)
            b = Cat(b)[:rng.randint(1, min(3, len(b)))] # Unsigned.
            return (a << b) if op == "<<" else (a >> b)
        b = self.expr(depth + 1)
        return {
            "+": a + b, "-": a - b, "*": a * b, "&": a & b, "|": a | b, "^": a ^ b,
            "<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "==": a == b, "!=": a != b,
        }[op]

class FuzzModule(Module):
    """Random expressions in the Verilog contexts, outputs o<n> (comb)."""
    def __init__(self, fuzzer, n_exprs=32):
        rng = fuzzer.rng
        self.inputs  = fuzzer.inputs
        self.outputs = []
        self.refs    = [] # (output, reference function of env).
        self.exprs   = [] # (expression, context).
        def add(o, ref):
            self.outputs.append(o)
            self.refs.append((o, ref))
            self.exprs.append((e, context))
        for n in range(n_exprs):
            e = fuzzer.expr()
            context = rng.choice(["assign", "assign", "if", "cat", "shift", "compare", "case", "mux"])
            if context == "assign":
                # Target narrower or wider than the expression.
                o = Signal((rng.randint(1, max(len(e) + 4, 2)), rng.random() < 0.3), name=f"o{n}")
                self.comb += o.eq(e)
                add(o, lambda env, e=e, o=o: truncate(ref_eval(e, env), len(o), o.signed))
            elif context == "if":
                o = Signal(name=f"o{n}")
                self.comb += If(e, o.eq(1)).Else(o.eq(0))
                add(o, lambda env, e=e: int((ref_eval(e, env) & ((1 << len(e)) - 1)) != 0))
            elif context == "case":
                # Case on the expression (simulator: test truncated to its width/signedness).
                o = Signal(2, name=f"o{n}")
                self.comb += Case(e, {0: o.eq(1), 1: o.eq(2), "default": o.eq(3)})
                def case_ref(env, e=e):
                    nbits, signed = value_bits_sign(e)
                    t = truncate(ref_eval(e, env), nbits, signed)
                    return {0: 1, 1: 2}.get(t, 3)
                add(o, case_ref)
            elif context == "mux":
                # Expression as a Mux condition (all its bits).
                o = Signal(name=f"o{n}")
                self.comb += o.eq(Mux(e, 1, 0))
                add(o, lambda env, e=e: int(ref_eval(e, env) != 0))
            elif context == "cat":
                c = fuzzer.leaf()
                o = Signal(len(e) + len(c), name=f"o{n}")
                self.comb += o.eq(Cat(e, c))
                add(o, lambda env, e=e, c=c: ref_eval(Cat(e, c), env))
            elif context == "shift":
                # Expression as a shift amount (unsigned, 1-3 bits used).
                x = fuzzer.leaf()
                s = Cat(e)[:min(3, len(e))]
                o = Signal(len(x) + 7, name=f"o{n}")
                self.comb += o.eq(x << s)
                add(o, lambda env, x=x, s=s, o=o: truncate(ref_eval(x << s, env), len(o), False))
            else:
                # Expression as a comparison operand.
                c = fuzzer.leaf()
                o = Signal(name=f"o{n}")
                self.comb += o.eq(e > c)
                add(o, lambda env, e=e, c=c: int(ref_eval(e, env) > ref_eval(c, env)))

# Verilator Evaluation -----------------------------------------------------------------------------

VERILATOR_MAIN = r"""
#include <cstdio>
#include <cstdint>
#include "Vtop.h"
int main() {
    Vtop top;
    unsigned long long v[%(n_in)d];
    while (true) {
        for (int i = 0; i < %(n_in)d; i++)
            if (scanf("%%llx", &v[i]) != 1) return 0;
%(set_inputs)s
        top.eval();
%(print_outputs)s
        printf("\n");
    }
}
"""

def verilator_available():
    return shutil.which("verilator") is not None

def verilator_eval(module, vectors, build_dir=None):
    """Outputs values (unsigned) of module (inputs/outputs Signals) for the input vectors."""
    inputs, outputs = module.inputs, module.outputs
    build_dir = build_dir or tempfile.mkdtemp(prefix="litex_verilog_semantics_")
    os.makedirs(build_dir, exist_ok=True)
    convert(module, ios=set(inputs) | set(outputs), name="top").write(os.path.join(build_dir, "top.v"))
    with open(os.path.join(build_dir, "main.cpp"), "w") as f:
        f.write(VERILATOR_MAIN % {
            "n_in"          : len(inputs),
            "set_inputs"    : "\n".join(f"        top.{s.name_override} = v[{i}];"
                for i, s in enumerate(inputs)),
            "print_outputs" : "\n".join(f"        printf(\"%llx \", (unsigned long long)top.{s.name_override});"
                for s in outputs),
        })
    subprocess.run(["verilator", "--cc", "--exe", "--build", "-Wno-fatal", "-Wno-lint", "-Wno-style",
        "top.v", "main.cpp", "-o", "sim"], cwd=build_dir, check=True, capture_output=True)
    stdin = "\n".join(" ".join(f"{(v & ((1 << len(s)) - 1)):x}" for s, v in zip(inputs, vector))
        for vector in vectors) + "\n"
    out = subprocess.run([os.path.join(build_dir, "obj_dir", "sim")], input=stdin, capture_output=True,
        text=True, check=True).stdout
    return [[int(x, 16) for x in line.split()] for line in out.strip().split("\n")]

def random_vectors(module, rng, n):
    vectors = []
    for _ in range(n):
        vectors.append([truncate(rng.getrandbits(len(s)), len(s), s.signed) for s in module.inputs])
    return vectors

def check_verilog(seed, n_exprs=32, n_vectors=64, build_dir=None, **kwargs):
    """Mismatches (expression index, vector, expected, got) of the Verilog generation for seed."""
    fuzzer = ExpressionFuzzer(seed, **kwargs)
    module = FuzzModule(fuzzer, n_exprs)
    vectors = random_vectors(module, fuzzer.rng, n_vectors)
    results = verilator_eval(module, vectors, build_dir)
    mismatches = []
    for vector, result in zip(vectors, results):
        env = dict(zip(module.inputs, vector))
        for n, ((o, ref), got) in enumerate(zip(module.refs, result)):
            expected = ref(env) & ((1 << len(o)) - 1)
            if got != expected:
                mismatches.append((n, o, vector, expected, got))
    return module, mismatches

# Simulator Evaluation -----------------------------------------------------------------------------

def check_simulator(seed, n_exprs=32, n_vectors=64, **kwargs):
    """Mismatches of the simulator (litex.gen.sim) for seed (same expressions/vectors as
    check_verilog)."""
    from litex.gen.sim import run_simulation
    fuzzer  = ExpressionFuzzer(seed, **kwargs)
    module  = FuzzModule(fuzzer, n_exprs)
    vectors = random_vectors(module, fuzzer.rng, n_vectors)
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
    mismatches = []
    for vector, result in zip(vectors, results):
        env = dict(zip(module.inputs, vector))
        for n, ((o, ref), got) in enumerate(zip(module.refs, result)):
            expected = ref(env) & ((1 << len(o)) - 1)
            if got != expected:
                mismatches.append((n, o, vector, expected, got))
    return module, mismatches
