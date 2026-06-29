#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Int Formatting -----------------------------------------------------------------------------------

def _is_power_of_two(value):
    return (value != 0) and ((value & (value - 1)) == 0)

def _is_bit_mask(value):
    return (value != 0) and _is_power_of_two(value + 1)

def _format_int_as_hex(value):
    value = abs(value)

    # Keep small values/counts readable.
    if value < 100:
        return False

    # Keep exact powers of 10 in decimal.
    decimal = str(value)
    if decimal[0] == "1" and set(decimal[1:]) <= {"0"}:
        return False

    # Powers/masks are more naturally read in hex once they are not tiny.
    if value >= 0x100 and _is_power_of_two(value):
        return True
    if value >= 0xff and _is_bit_mask(value):
        return True

    # Aligned values are usually addresses/sizes/register values.
    if value >= 0x1000 and (value & 0xff) == 0:
        return True

    # For larger unstructured values, use hex when it is visibly simpler.
    hexadecimal = f"{value:x}"
    if value >= 0x10000 and len(set(hexadecimal)) < len(set(decimal)):
        return True

    return False

def format_int(value, prefix="0x", suffix="", base="auto"):
    if base not in ["auto", "dec", "hex"]:
        raise ValueError("base must be auto, dec or hex")
    if value < 0:
        return f"-{format_int(-value, prefix=prefix, suffix=suffix, base=base)}"
    if base == "hex" or (base == "auto" and _format_int_as_hex(value)):
        return f"{prefix}{value:x}{suffix}"
    return f"{value:d}{suffix}"

def format_verilog_int(value, base="auto"):
    if value < 0:
        return f"-{format_verilog_int(-value, base=base)}"
    value = format_int(value, prefix="h", base=base)
    return value if value.startswith("h") else f"d{value}"
