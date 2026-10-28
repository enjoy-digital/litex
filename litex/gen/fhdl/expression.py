#
# This file is part of LiteX (Adapted from Migen for LiteX usage).
#
# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2013-2023 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from enum import IntEnum

from migen.fhdl.structure import *
from migen.fhdl.structure import _Operator, _Slice, _Assign, _Fragment
from migen.fhdl.bitcontainer import value_bits_sign

from litex.gen.format import format_verilog_int

# ------------------------------------------------------------------------------------------------ #
#                                       EXPRESSIONS                                                #
# ------------------------------------------------------------------------------------------------ #

# Print Constant -----------------------------------------------------------------------------------

def _generate_constant(node):
    # -N'hX is unary minus on an *unsigned* literal, so any comparison against it turns unsigned
    # and inverts for positive operands. Emit the two's-complement pattern as $signed() instead.
    if node.signed and node.value < 0:
        pattern = (1 << node.nbits) + node.value
        return f"$signed({node.nbits}'{format_verilog_int(pattern)})", True
    # Signed positive constant: N'sdV (N'dV is unsigned in Verilog, turning the expression unsigned).
    return "{bits}'{sign}{value}".format(
        bits  = str(node.nbits),
        sign  = "s" if node.signed else "",
        value = format_verilog_int(node.value),
    ), node.signed

# Print Signal -------------------------------------------------------------------------------------

def _generate_signal(ns, s):
    length = 8
    vector = f"[{str(len(s)-1)}:0] "
    vector = " "*(length-len(vector)) + vector
    return "{signed}{vector}{name}".format(
        signed = " " if (not s.signed) else "signed ",
        vector = " "*length if (len(s) <= 1) else vector,
        name   = ns.get_name(s)
    )

# Expressions Widths -------------------------------------------------------------------------------
#
# The expressions are generated with the simulator semantics: exact integer arithmetic (no
# truncation inside the expressions, values truncated to their target on assignment), the bitwise
# inversion of an unsigned value has the width of its operand (Migen width rules).
#
# Verilog sizes the operands of an expression from its context (all the operands of the
# context-determined operators, and the assignment target) and evaluates it on this width: results
# are truncated when the context is narrower than the exact result (self-determined contexts:
# comparisons operands, shift amounts, concatenations, conditions...) and inverted unsigned values
# get their extension bits inverted when the context is wider. Each node is generated with the
# number of exact low bits needed by its consumer (need, None: all of them) and a lower bound of the
# width it is evaluated on (width): sized zero added to the arithmetic results (+ N'd0) and
# inverted unsigned values masked only when needed.

def _bitwise_bits_sign(a, b):
    (na, sa), (nb, sb) = a, b
    if sa == sb:
        return max(na, nb), sa
    return (max(na + 1, nb) if sb else max(na, nb + 1)), True

def _bits_sign(node):
    """Exact width/signedness of the value of node (Migen width rules, except the signed
    multiplication and the unary minus which need one more bit for their extreme values)."""
    if isinstance(node, _Operator):
        obs = [_bits_sign(o) for o in node.operands]
        op  = node.op
        if len(obs) == 1:
            if op == "-":
                return obs[0][0] + 1, True
            return obs[0]
        if op in ["+", "-"]:
            n, s = _bitwise_bits_sign(*obs)
            return n + 1, s
        if op == "*":
            return obs[0][0] + obs[1][0], obs[0][1] or obs[1][1]
        if op == "<<<":
            return obs[0][0] + 2**obs[1][0] - 1, obs[0][1]
        if op == ">>>":
            return obs[0]
        if op in ["&", "|", "^"]:
            return _bitwise_bits_sign(*obs)
        if op == "m":
            return _bitwise_bits_sign(obs[1], obs[2])
        return 1, False # Comparisons.
    return value_bits_sign(node)

def _verilog_width(node):
    """Lower bound of the Verilog self-determined width of node."""
    if isinstance(node, _Operator):
        op = node.op
        if op in ["<", "<=", "==", "!=", ">", ">="]:
            return 1
        if op in ["~", "<<<", ">>>"] or len(node.operands) == 1:
            return _verilog_width(node.operands[0])
        if op == "m":
            return max(_verilog_width(node.operands[1]), _verilog_width(node.operands[2]))
        return max(_verilog_width(o) for o in node.operands)
    return len(node)

def _needs(need, width):
    """Exact low bits needed beyond the evaluation width."""
    return (need is None) or (need > width)

def _target(need, n):
    """Width to evaluate a n-bit (exact) result on for need bits."""
    return n if need is None else min(need, n)

# Print Operator -----------------------------------------------------------------------------------

class OperatorType(IntEnum):
   UNARY   = 1
   BINARY  = 2
   TERNARY = 3

def _to_signed(r):
    return f"$signed({{1'd0, {r}}})"

def _pad(r, s, n):
    """r evaluated on at least n bits (sized zero added to the context-determined operation)."""
    return f"(({r}) + {n}'{'s' if s else ''}d0)"

def _generate_operand(ns, node, need, width, signed):
    """Generate an operand of a context-determined operation (on width), converted to signed when
    signed (the conversion is self-determined: the operand is then generated on its own width)."""
    r, s, w = _generate_expression(ns, node, need, width)
    if signed and not s:
        r, s, w = _generate_expression(ns, node, need, _verilog_width(node))
        if not s:
            r, s, w = _to_signed(r), True, w + 1
    return r, s, w

def _generate_operator(ns, node, need, width):
    operator = node.op
    operands = node.operands
    arity    = len(operands)
    assert arity in [item.value for item in OperatorType]
    n, sn = _bits_sign(node)
    width = max(width, _verilog_width(node))

    # Unary Operator.
    if arity == OperatorType.UNARY:
        a_n, a_s = _bits_sign(operands[0])
        # Negation Operator (exact: signed, one more bit).
        if operator == "-":
            r1, s1, w1 = _generate_operand(ns, operands[0], need, width, signed=True)
            r, s, w = "-" + r1, True, w1
            if _needs(need, max(width, w)) and (max(width, w) < n):
                r, w = _pad(r, s, _target(need, n)), _target(need, n)
        # Inversion of an unsigned value: width of its operand (masked when its extension bits
        # are used).
        elif operator == "~" and not a_s:
            a_need = a_n if need is None else min(need, a_n)
            r1, s1, w1 = _generate_expression(ns, operands[0], a_need, width)
            r, s, w = "~" + r1, s1, w1
            if _needs(need, a_n):
                r, s = f"{r} & {a_n}'d{(1 << a_n) - 1}", False
        # Other Operators.
        else:
            r1, s1, w1 = _generate_expression(ns, operands[0], need, width)
            r, s, w = operator + r1, s1, w1

    # Binary Operator.
    if arity == OperatorType.BINARY:
        a, b = operands
        # Shifts: amount self-determined (exact), right shifted value exact.
        if operator in ["<<<", ">>>"]:
            r1, s1, w1 = _generate_expression(ns, a, need if operator == "<<<" else None, width)
            r2, s2, w2 = _generate_expression(ns, b, None, _verilog_width(b))
            r, s, w = f"{r1} {operator} {r2}", s1, w1
            if operator == "<<<" and _needs(need, max(width, w)) and (max(width, w) < n):
                r, w = _pad(r, s, _target(need, n)), _target(need, n)
        # Comparisons: operands exact (own context).
        elif operator in ["<", "<=", "==", "!=", ">", ">="]:
            cwidth = max(_verilog_width(a), _verilog_width(b))
            r1, s1, w1 = _generate_expression(ns, a, None, cwidth)
            r2, s2, w2 = _generate_expression(ns, b, None, cwidth)
            if s1 != s2:
                r1, s1, w1 = _generate_operand(ns, a, None, cwidth, signed=True)
                r2, s2, w2 = _generate_operand(ns, b, None, cwidth, signed=True)
            r, s, w = f"{r1} {operator} {r2}", False, 1
        # Arithmetic/Bitwise Operators.
        else:
            a_need = need
            r1, s1, w1 = _generate_expression(ns, a, a_need, width)
            r2, s2, w2 = _generate_expression(ns, b, a_need, width)
            # Unsigned subtraction with its exact (negative) value used: signed.
            signed = s1 or s2 or (operator == "-" and _needs(need, width))
            if signed:
                r1, s1, w1 = _generate_operand(ns, a, a_need, width, signed=True)
                r2, s2, w2 = _generate_operand(ns, b, a_need, width, signed=True)
            r, s, w = f"{r1} {operator} {r2}", signed, max(w1, w2)
            if operator in ["+", "-", "*"] and _needs(need, max(width, w)) and (max(width, w) < n):
                r, w = _pad(r, s, _target(need, n)), _target(need, n)

    # Ternary Operator.
    if arity == OperatorType.TERNARY:
        assert operator == "m"
        r1, s1, w1 = _generate_expression(ns, operands[0], None, _verilog_width(operands[0]))
        r2, s2, w2 = _generate_expression(ns, operands[1], need, width)
        r3, s3, w3 = _generate_expression(ns, operands[2], need, width)
        if s2 != s3:
            r2, s2, w2 = _generate_operand(ns, operands[1], need, width, signed=True)
            r3, s3, w3 = _generate_operand(ns, operands[2], need, width, signed=True)
        r, s, w = f"{r1} ? {r2} : {r3}", s2 or s3, max(w2, w3)

    return f"({r})", s, w

# Print Slice --------------------------------------------------------------------------------------

def _generate_slice(ns, node):
    assert (node.stop - node.start) >= 1
    if hasattr(node.value, "__len__") and len(node.value) == 1:
         sr = "" # Avoid slicing 1-bit Signals.
    else:
        if (node.stop - node.start) > 1:
            sr = f"[{node.stop-1}:{node.start}]"
        else:
            sr = f"[{node.start}]"
    r, s, w = _generate_expression(ns, node.value)
    # Part-select: unsigned (a 1-bit signed Signal, not sliced, is converted).
    if (sr == "") and s:
        return f"$unsigned({r})", False, 1
    return r + sr, False, node.stop - node.start

# Print Cat ----------------------------------------------------------------------------------------

def _generate_concat_element(ns, node):
    """Concatenation element (self-determined) on its width (len)."""
    n = len(node)
    r, s, w = _generate_expression(ns, node, n, _verilog_width(node))
    assert w <= n, (r, w, n)
    if w < n:
        r = _pad(r, s, n)
    return r

def _generate_cat(ns, node):
    l = [_generate_concat_element(ns, v) for v in reversed(node.l)]
    return "{" + ", ".join(l) + "}", False, len(node)

# Print Replicate ----------------------------------------------------------------------------------

def _generate_replicate(ns, node):
    return "{" + str(node.n) + "{" + _generate_concat_element(ns, node.v) + "}}", False, len(node)

# Print Expression ---------------------------------------------------------------------------------

def _generate_expression(ns, node, need=None, width=None):
    """Verilog expression of node: (expression, signed, width).

    need : exact low bits of the value needed by the consumer (None: all, ex: comparisons operands).
    width: (lower bound of the) width the expression is evaluated on by its context (None: its own
           width, self-determined), ex: assignment target width.
    """
    if width is None:
        width = _verilog_width(node)

    # Constant.
    if isinstance(node, Constant):
        r, s = _generate_constant(node)
        return r, s, node.nbits

    # Signal.
    elif isinstance(node, Signal):
        return ns.get_name(node), node.signed, len(node)

    # Operator.
    elif isinstance(node, _Operator):
        return _generate_operator(ns, node, need, width)

    # Slice.
    elif isinstance(node, _Slice):
        return _generate_slice(ns, node)

    # Cat.
    elif isinstance(node, Cat):
        return _generate_cat(ns, node)

    # Replicate.
    elif isinstance(node, Replicate):
        return _generate_replicate(ns, node)

    # Unknown.
    else:
        raise TypeError(f"Expression of unrecognized type: '{type(node).__name__}'")
