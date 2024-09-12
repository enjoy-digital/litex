#
# This file is part of LiteX.
#
# This file is Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from functools import reduce
from operator import and_, or_, not_, xor, add

# Reduction ----------------------------------------------------------------------------------------

def Reduce(operator, value):
    # List of supported Operators.
    operators = {
        "AND"  : and_,
        "OR"   : or_,
        "NOR"  : not_,
        "XOR"  : xor,
        "ADD"  : add,
    }

    # Switch to upper-case.
    operator = operator.upper()

    # Check if provided operator is supported.
    if operator not in operators.keys():
        supported = ", ".join(operators.keys())
        raise ValueError(f"Reduce does not support {operator} operator; supported: {supported}.")

    # Return Python's reduction.
    return reduce(operators[operator], value)
