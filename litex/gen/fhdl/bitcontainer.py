from litex.gen.fhdl import structure as f


__all__ = ["log2_int", "bits_for", "value_bits_sign"]


def log2_int(n, need_pow2=True):
    if n == 0:
        return 0
    r = (n - 1).bit_length()
    if need_pow2 and (1 << r) != n:
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


def _bitwise_binary_bits_sign(a, b):
    if not a[1] and not b[1]:
        # both operands unsigned
        return max(a[0], b[0]), False
    elif a[1] and b[1]:
        # both operands signed
        return max(a[0], b[0]), True
    elif not a[1] and b[1]:
        # first operand unsigned (add sign bit), second operand signed
        return max(a[0] + 1, b[0]), True
    else:
        # first signed, second operand unsigned (add sign bit)
        return max(a[0], b[0] + 1), True


def value_bits_sign(v):
    """Bit length and signedness of a value.

    Parameters
    ----------
    v : Value

    Returns
    -------
    int, bool
        Number of bits required to store `v` or available in `v`, followed by
        whether `v` has a sign bit (included in the bit count).

    Examples
    --------
    >>> value_bits_sign(f.Signal(8))
    8, False
    >>> value_bits_sign(C(0xaa))
    8, False
    """
    if isinstance(v, (f.Constant, f.Signal)):
        return v.nbits, v.signed
    elif isinstance(v, (f.ClockSignal, f.ResetSignal)):
        return 1, False
    elif isinstance(v, f._Operator):
        obs = list(map(value_bits_sign, v.operands))
        if v.op == "+" or v.op == "-":
            if len(obs) == 1:
                if v.op == "-" and not obs[0][1]:
                    return obs[0][0] + 1, True
                else:
                    return obs[0]
            n, s = _bitwise_binary_bits_sign(*obs)
            return n + 1, s
        elif v.op == "*":
            if not obs[0][1] and not obs[1][1]:
                # both operands unsigned
                return obs[0][0] + obs[1][0], False
            elif obs[0][1] and obs[1][1]:
                # both operands signed
                return obs[0][0] + obs[1][0] - 1, True
            else:
                # one operand signed, the other unsigned (add sign bit)
                return obs[0][0] + obs[1][0] + 1 - 1, True
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
            return _bitwise_binary_bits_sign(*obs)
        elif (v.op == "<" or v.op == "<=" or v.op == "==" or v.op == "!=" or
              v.op == ">" or v.op == ">="):
            return 1, False
        elif v.op == "~":
            return obs[0]
        elif v.op == "m":
            return _bitwise_binary_bits_sign(obs[1], obs[2])
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
