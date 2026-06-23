#
# This file is part of LiteX (Adapted from Migen for LiteX usage).
#
# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2013-2023 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from enum import IntEnum

from migen.fhdl.structure import *
from migen.fhdl.structure import _Operator, _Slice, _Assign, _Fragment

# ------------------------------------------------------------------------------------------------ #
#                                       EXPRESSIONS                                                #
# ------------------------------------------------------------------------------------------------ #

# Print Constant -----------------------------------------------------------------------------------

def _generate_constant(node):
    return "{sign}{bits}'d{value}".format(
        sign  = "" if node.value >= 0 else "-",
        bits  = str(node.nbits),
        value = abs(node.value),
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

# Print Operator -----------------------------------------------------------------------------------

class OperatorType(IntEnum):
   UNARY   = 1
   BINARY  = 2
   TERNARY = 3

def _generate_operator(ns, node):
    operator = node.op
    operands = node.operands
    arity    = len(operands)
    assert arity in [item.value for item in OperatorType]

    def to_signed(r):
        return f"$signed({{1'd0, {r}}})"

    # Unary Operator.
    if arity == OperatorType.UNARY:
        r1, s1 = _generate_expression(ns, operands[0])
        # Negation Operator.
        if operator == "-":
            # Negate and convert to signed if not already.
            r = "-" + (r1 if s1 else to_signed(r1))
            s = True
        # Other Operators.
        else:
            r = operator + r1
            s = s1

    # Binary Operator.
    if arity == OperatorType.BINARY:
        r1, s1 = _generate_expression(ns, operands[0])
        r2, s2 = _generate_expression(ns, operands[1])
        # Convert all expressions to signed when at least one is signed.
        if operator not in ["<<<", ">>>"]:
            if s2 and not s1:
                r1 = to_signed(r1)
            if s1 and not s2:
                r2 = to_signed(r2)
        r = f"{r1} {operator} {r2}"
        s = s1 or s2

    # Ternary Operator.
    if arity == OperatorType.TERNARY:
        assert operator == "m"
        r1, s1 = _generate_expression(ns, operands[0])
        r2, s2 = _generate_expression(ns, operands[1])
        r3, s3 = _generate_expression(ns, operands[2])
        # Convert all expressions to signed when at least one is signed.
        if s2 and not s3:
            r3 = to_signed(r3)
        if s3 and not s2:
            r2 = to_signed(r2)
        r = f"{r1} ? {r2} : {r3}"
        s = s2 or s3

    return f"({r})", s

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
    r, s = _generate_expression(ns, node.value)
    return r + sr, s

# Print Cat ----------------------------------------------------------------------------------------

def _generate_cat(ns, node):
    l = [_generate_expression(ns, v)[0] for v in reversed(node.l)]
    return "{" + ", ".join(l) + "}", False

# Print Replicate ----------------------------------------------------------------------------------

def _generate_replicate(ns, node):
    return "{" + str(node.n) + "{" + _generate_expression(ns, node.v)[0] + "}}", False

# Print Expression ---------------------------------------------------------------------------------

def _generate_expression(ns, node):
    # Constant.
    if isinstance(node, Constant):
        return _generate_constant(node)

    # Signal.
    elif isinstance(node, Signal):
        return ns.get_name(node), node.signed

    # Operator.
    elif isinstance(node, _Operator):
        return _generate_operator(ns, node)

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
