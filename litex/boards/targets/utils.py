import pprint


def period_ns(freq):
    return 1e9/freq


def csr_map_update(csr_map, csr_peripherals):
    csr_map.update(dict((n, v)
        for v, n in enumerate(csr_peripherals, start=(max(csr_map.values()) + 1) if csr_map else 0)))


def csr_map_update_print(csr_map, csr_peripherals):
    print()
    print("-"*75)
    print("Previous Max: {}".format(max(csr_map.values())))
    csr_map.update(dict((n, v)
        for v, n in enumerate(csr_peripherals, start=max(csr_map.values()) + 1)))
    print("     New Max: {}".format(max(csr_map.values())))
    csr_values = list((b,a) for a, b in csr_map.items())
    csr_values.sort()
    pprint.pprint(csr_values)
    print("-"*75)
    print()


def assert_pll_clock(requested_freq, input, feedback, divide, msg):
    output_freq = int(input * feedback / divide / 1e6)
    assert output_freq == int(requested_freq / 1e6), (
        "%s wants %s but got %i MHz (input=%i MHz feedback=%i divide=%i)" % (
            msg, requested_freq, output_freq, int(input/1e6), feedback, divide))


class MHzType(int):
    """
    >>> a = MHzType(1)
    >>> a == int(1e9)
    True
    >>> a
    1 MHz
    >>> b = 5 * MHzType(1)
    >>> b == int(5e9)
    True
    >>> b
    5 MHz
    >>> c = 200 * MHzType(1)
    >>>
    """

    def __new__(cls, x):
        return int.__new__(cls, int(x * 1e6))

    def __str__(self):
        return "%i MHz" % int(self / 1e6)

    def __repr__(self):
        return "%f * MHz()" % float(self / 1e6)

    def __mul__(self, o):
        return MHz.__class__(float(self) * o / 1e6)

    def __rmul__(self, o):
        return MHz.__class__(float(self) * o / 1e6)

    def to_ns(self):
        return 1e9/self


MHz = MHzType(1)
