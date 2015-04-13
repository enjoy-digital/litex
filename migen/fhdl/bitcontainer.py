from migen.fhdl import structure as f

def log2_int(n, need_pow2=True):
    l = 1
    r = 0
    while l < n:
        l *= 2
        r += 1
    if need_pow2 and l != n:
        raise ValueError("Not a power of 2")
    return r

def bits_for(n, require_sign_bit=False):
    if n > 0:
        r = log2_int(n + 1, False)
    else:
        require_sign_bit = True
        r = log2_int(-n, False)
    if require_sign_bit:
        r += 1
    return r

def value_bits_sign(v):
    if isinstance(v, bool):
        return 1, False
    elif isinstance(v, int):
        return bits_for(v), v < 0
    elif isinstance(v, f.Signal):
        return v.nbits, v.signed
    elif isinstance(v, (f.ClockSignal, f.ResetSignal)):
        return 1, False
    elif isinstance(v, f._Operator):
        obs = list(map(value_bits_sign, v.operands))
        if v.op == "+" or v.op == "-":
            if not obs[0][1] and not obs[1][1]:
                # both operands unsigned
                return max(obs[0][0], obs[1][0]) + 1, False
            elif obs[0][1] and obs[1][1]:
                # both operands signed
                return max(obs[0][0], obs[1][0]) + 1, True
            elif not obs[0][1] and obs[1][1]:
                # first operand unsigned (add sign bit), second operand signed
                return max(obs[0][0] + 1, obs[1][0]) + 1, True
            else:
                # first signed, second operand unsigned (add sign bit)
                return max(obs[0][0], obs[1][0] + 1) + 1, True
        elif v.op == "*":
            if not obs[0][1] and not obs[1][1]:
                # both operands unsigned
                return obs[0][0] + obs[1][0]
            elif obs[0][1] and obs[1][1]:
                # both operands signed
                return obs[0][0] + obs[1][0] - 1
            else:
                # one operand signed, the other unsigned (add sign bit)
                return obs[0][0] + obs[1][0] + 1 - 1
        elif v.op == "<<<":
            if obs[1][1]:
                extra = 2**(obs[1][0] - 1) - 1
            else:
                extra = 2**obs[1][0] - 1
            return obs[0][0] + extra, obs[0][1]
        elif v.op == ">>>":
            if obs[1][1]:
                extra = 2**(obs[1][0] - 1)
            else:
                extra = 0
            return obs[0][0] + extra, obs[0][1]
        elif v.op == "&" or v.op == "^" or v.op == "|":
            if not obs[0][1] and not obs[1][1]:
                # both operands unsigned
                return max(obs[0][0], obs[1][0]), False
            elif obs[0][1] and obs[1][1]:
                # both operands signed
                return max(obs[0][0], obs[1][0]), True
            elif not obs[0][1] and obs[1][1]:
                # first operand unsigned (add sign bit), second operand signed
                return max(obs[0][0] + 1, obs[1][0]), True
            else:
                # first signed, second operand unsigned (add sign bit)
                return max(obs[0][0], obs[1][0] + 1), True
        elif v.op == "<" or v.op == "<=" or v.op == "==" or v.op == "!=" \
          or v.op == ">" or v.op == ">=":
              return 1, False
        elif v.op == "~":
            return obs[0]
        else:
            raise TypeError
    elif isinstance(v, f._Slice):
        return v.stop - v.start, value_bits_sign(v.value)[1]
    elif isinstance(v, f.Cat):
        return sum(value_bits_sign(sv)[0] for sv in v.l), False
    elif isinstance(v, f.Replicate):
        return (value_bits_sign(v.v)[0])*v.n, False
    elif isinstance(v, f._ArrayProxy):
        bsc = list(map(value_bits_sign, v.choices))
        return max(bs[0] for bs in bsc), any(bs[1] for bs in bsc)
    else:
        raise TypeError("Can not calculate bit length of {} {}".format(
            type(v), v))

def flen(v):
    """Bit length of an expression

    Parameters
    ----------
    v : int, bool or Value

    Returns
    -------
    int
        Number of bits required to store `v` or available in `v`

    Examples
    --------
    >>> flen(f.Signal(8))
    8
    >>> flen(0xaa)
    8
    """
    return value_bits_sign(v)[0]

def fiter(v):
    """Bit iterator

    Parameters
    ----------
    v : int, bool or Value

    Returns
    -------
    iter
        Iterator over the bits in `v`

    Examples
    --------
    >>> list(fiter(f.Signal(2))) #doctest: +ELLIPSIS
    [<migen.fhdl.structure._Slice object at 0x...>, <migen.fhdl.structure._Slice object at 0x...>]
    >>> list(fiter(4))
    [0, 0, 1]
    """
    if isinstance(v, (bool, int)):
        return ((v >> i) & 1 for i in range(bits_for(v)))
    elif isinstance(v, f.Value):
        return (v[i] for i in range(flen(v)))
    else:
        raise TypeError("Can not bit-iterate {} {}".format(type(v), v))

def fslice(v, s):
    """Bit slice

    Parameters
    ----------
    v : int, bool or Value
    s : slice or int

    Returns
    -------
    int or Value
        Expression for the slice `s` of `v`.

    Examples
    --------
    >>> fslice(f.Signal(2), 1) #doctest: +ELLIPSIS
    <migen.fhdl.structure._Slice object at 0x...>
    >>> bin(fslice(0b1101, slice(1, None, 2)))
    '0b10'
    >>> fslice(-1, slice(0, 4))
    1
    >>> fslice(-7, slice(None))
    9
    """
    if isinstance(v, (bool, int)):
        if isinstance(s, int):
            s = slice(s)
        idx = range(*s.indices(bits_for(v)))
        return sum(((v >> i) & 1) << j for j, i in enumerate(idx))
    elif isinstance(v, f.Value):
        return v[s]
    else:
        raise TypeError("Can not bit-slice {} {}".format(type(v), v))

def freversed(v):
    """Bit reverse

    Parameters
    ----------
    v : int, bool or Value

    Returns
    -------
    int or Value
        Expression containing the bit reversed input.

    Examples
    --------
    >>> freversed(f.Signal(2)) #doctest: +ELLIPSIS
    <migen.fhdl.structure.Cat object at 0x...>
    >>> bin(freversed(0b1011))
    '0b1101'
    """
    return fslice(v, slice(None, None, -1))
