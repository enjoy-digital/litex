
def format_constant(c, verilog:bool = False):
    """Automatically format constants based on type and value.

    If the argument `verilog` isn't provided, a 'c' style constant is generated.

    Integer constants are formatted as decimal or hexadecimal depending on which
    value will give the clearest representation, as indicated by the least unique
    numbers in the string representation.

    NOTE: Integers below 100 are always formatted as decimal.

    Parameters
    ----------
    c : any
        constant to format. Only integer constants are formatted.

    verilog : bool, optional
        Format for verilog (default is False)

    Raises
    ------
    None
    """

    if not isinstance(c, int):
        return c

    d, x = f"{c:d}", f"{c:x}"
    decimal = abs(c) < 100 or len(set(d)) <= len(set(x))
    if verilog:
        return "d" + d if decimal else "h" + x
    else:
        return d if decimal else "0x" + x
