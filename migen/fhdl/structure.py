import builtins as _builtins
import collections as _collections

from migen.fhdl import tracer as _tracer
from migen.util.misc import flat_iteration as _flat_iteration


class DUID:
    """Deterministic Unique IDentifier"""
    __next_uid = 0
    def __init__(self):
        self.duid = DUID.__next_uid
        DUID.__next_uid += 1


class _Value(DUID):
    """Base class for operands

    Instances of `_Value` or its subclasses can be operands to
    arithmetic, comparison, bitwise, and logic operators.
    They can be assigned (:meth:`eq`) or indexed/sliced (using the usual
    Python indexing and slicing notation).

    Values created from integers have the minimum bit width to necessary to
    represent the integer.
    """
    def __bool__(self):
        # Special case: Constants and Signals are part of a set or used as
        # dictionary keys, and Python needs to check for equality.
        if isinstance(self, _Operator) and self.op == "==":
            a, b = self.operands
            if isinstance(a, Constant) and isinstance(b, Constant):
                return a.value == b.value
            if isinstance(a, Signal) and isinstance(b, Signal):
                return a is b
            if (isinstance(a, Constant) and isinstance(b, Signal)
                    or isinstance(a, Signal) and isinstance(a, Constant)):
                return False
        raise TypeError("Attempted to convert Migen value to boolean")

    def __invert__(self):
        return _Operator("~", [self])
    def __neg__(self):
        return _Operator("-", [self])

    def __add__(self, other):
        return _Operator("+", [self, other])
    def __radd__(self, other):
        return _Operator("+", [other, self])
    def __sub__(self, other):
        return _Operator("-", [self, other])
    def __rsub__(self, other):
        return _Operator("-", [other, self])
    def __mul__(self, other):
        return _Operator("*", [self, other])
    def __rmul__(self, other):
        return _Operator("*", [other, self])
    def __lshift__(self, other):
        return _Operator("<<<", [self, other])
    def __rlshift__(self, other):
        return _Operator("<<<", [other, self])
    def __rshift__(self, other):
        return _Operator(">>>", [self, other])
    def __rrshift__(self, other):
        return _Operator(">>>", [other, self])
    def __and__(self, other):
        return _Operator("&", [self, other])
    def __rand__(self, other):
        return _Operator("&", [other, self])
    def __xor__(self, other):
        return _Operator("^", [self, other])
    def __rxor__(self, other):
        return _Operator("^", [other, self])
    def __or__(self, other):
        return _Operator("|", [self, other])
    def __ror__(self, other):
        return _Operator("|", [other, self])

    def __lt__(self, other):
        return _Operator("<", [self, other])
    def __le__(self, other):
        return _Operator("<=", [self, other])
    def __eq__(self, other):
        return _Operator("==", [self, other])
    def __ne__(self, other):
        return _Operator("!=", [self, other])
    def __gt__(self, other):
        return _Operator(">", [self, other])
    def __ge__(self, other):
        return _Operator(">=", [self, other])

    def __len__(self):
        from migen.fhdl.bitcontainer import value_bits_sign
        return value_bits_sign(self)[0]

    def __getitem__(self, key):
        n = len(self)
        if isinstance(key, int):
            if key >= n:
                raise IndexError
            if key < 0:
                key += n
            return _Slice(self, key, key+1)
        elif isinstance(key, slice):
            start, stop, step = key.indices(n)
            if step != 1:
                return Cat(self[i] for i in range(start, stop, step))
            return _Slice(self, start, stop)
        else:
            raise TypeError

    def eq(self, r):
        """Assignment

        Parameters
        ----------
        r : _Value, in
            Value to be assigned.

        Returns
        -------
        _Assign
            Assignment statement that can be used in combinatorial or
            synchronous context.
        """
        return _Assign(self, r)

    def __hash__(self):
        raise TypeError("unhashable type: '{}'".format(type(self).__name__))


def wrap(value):
    """Ensures that the passed object is a Migen value. Booleans and integers
    are automatically wrapped into ``Constant``."""
    if isinstance(value, (bool, int)):
        value = Constant(value)
    if not isinstance(value, _Value):
        raise TypeError("Object is not a Migen value")
    return value


class _Operator(_Value):
    def __init__(self, op, operands):
        _Value.__init__(self)
        self.op = op
        self.operands = [wrap(o) for o in operands]


def Mux(sel, val1, val0):
    """Multiplex between two values

    Parameters
    ----------
    sel : _Value(1), in
        Selector.
    val1 : _Value(N), in
    val0 : _Value(N), in
        Input values.

    Returns
    -------
    _Value(N), out
        Output `_Value`. If `sel` is asserted, the Mux returns
        `val1`, else `val0`.
    """
    return _Operator("m", [sel, val1, val0])


class _Slice(_Value):
    def __init__(self, value, start, stop):
        _Value.__init__(self)
        if not isinstance(start, int) or not isinstance(stop, int):
            raise TypeError("Slice boundaries must be integers")
        self.value = wrap(value)
        self.start = start
        self.stop = stop


class Cat(_Value):
    """Concatenate values

    Form a compound `_Value` from several smaller ones by concatenation.
    The first argument occupies the lower bits of the result.
    The return value can be used on either side of an assignment, that
    is, the concatenated value can be used as an argument on the RHS or
    as a target on the LHS. If it is used on the LHS, it must solely
    consist of `Signal` s, slices of `Signal` s, and other concatenations
    meeting these properties. The bit length of the return value is the sum of
    the bit lengths of the arguments::

        len(Cat(args)) == sum(len(arg) for arg in args)

    Parameters
    ----------
    *args : _Values or iterables of _Values, inout
        `_Value` s to be concatenated.

    Returns
    -------
    Cat, inout
        Resulting `_Value` obtained by concatentation.
    """
    def __init__(self, *args):
        _Value.__init__(self)
        self.l = [wrap(v) for v in _flat_iteration(args)]


class Replicate(_Value):
    """Replicate a value

    An input value is replicated (repeated) several times
    to be used on the RHS of assignments::

        len(Replicate(s, n)) == len(s)*n

    Parameters
    ----------
    v : _Value, in
        Input value to be replicated.
    n : int
        Number of replications.

    Returns
    -------
    Replicate, out
        Replicated value.
    """
    def __init__(self, v, n):
        _Value.__init__(self)
        if not isinstance(n, int) or n < 0:
            raise TypeError("Replication count must be a positive integer")
        self.v = wrap(v)
        self.n = n


class Constant(_Value):
    """A constant, HDL-literal integer `_Value`

    Parameters
    ----------
    value : int
    bits_sign : int or tuple or None
        Either an integer `bits` or a tuple `(bits, signed)`
        specifying the number of bits in this `Constant` and whether it is
        signed (can represent negative values). `bits_sign` defaults
        to the minimum width and signedness of `value`.
    """
    def __init__(self, value, bits_sign=None):
        from migen.fhdl.bitcontainer import bits_for

        _Value.__init__(self)

        self.value = int(value)
        if bits_sign is None:
            bits_sign = bits_for(self.value), self.value < 0
        elif isinstance(bits_sign, int):
            bits_sign = bits_sign, self.value < 0
        self.nbits, self.signed = bits_sign
        if not isinstance(self.nbits, int) or self.nbits <= 0:
            raise TypeError("Width must be a strictly positive integer")

    def __hash__(self):
        return self.value


C = Constant  # shorthand


class Signal(_Value):
    """A `_Value` that can change

    The `Signal` object represents a value that is expected to change
    in the circuit. It does exactly what Verilog's `wire` and
    `reg` and VHDL's `signal` do.

    A `Signal` can be indexed to access a subset of its bits. Negative
    indices (`signal[-1]`) and the extended Python slicing notation
    (`signal[start:stop:step]`) are supported.
    The indices 0 and -1 are the least and most significant bits
    respectively.

    Parameters
    ----------
    bits_sign : int or tuple
        Either an integer `bits` or a tuple `(bits, signed)`
        specifying the number of bits in this `Signal` and whether it is
        signed (can represent negative values). `signed` defaults to
        `False`.
    name : str or None
        Name hint for this signal. If `None` (default) the name is
        inferred from the variable name this `Signal` is assigned to.
        Name collisions are automatically resolved by prepending
        names of objects that contain this `Signal` and by
        appending integer sequences.
    variable : bool
        Deprecated.
    reset : int
        Reset (synchronous) or default (combinatorial) value.
        When this `Signal` is assigned to in synchronous context and the
        corresponding clock domain is reset, the `Signal` assumes the
        given value. When this `Signal` is unassigned in combinatorial
        context (due to conditional assignments not being taken),
        the `Signal` assumes its `reset` value. Defaults to 0.
    name_override : str or None
        Do not use the inferred name but the given one.
    min : int or None
    max : int or None
        If `bits_sign` is `None`, the signal bit width and signedness are
        determined by the integer range given by `min` (inclusive,
        defaults to 0) and `max` (exclusive, defaults to 2).
    related : Signal or None
    """
    def __init__(self, bits_sign=None, name=None, variable=False, reset=0, name_override=None, min=None, max=None, related=None):
        from migen.fhdl.bitcontainer import bits_for

        _Value.__init__(self)

        # determine number of bits and signedness
        if bits_sign is None:
            if min is None:
                min = 0
            if max is None:
                max = 2
            max -= 1  # make both bounds inclusive
            assert(min < max)
            self.signed = min < 0 or max < 0
            self.nbits = _builtins.max(bits_for(min, self.signed), bits_for(max, self.signed))
        else:
            assert(min is None and max is None)
            if isinstance(bits_sign, tuple):
                self.nbits, self.signed = bits_sign
            else:
                self.nbits, self.signed = bits_sign, False
        if not isinstance(self.nbits, int) or self.nbits <= 0:
            raise ValueError("Signal width must be a strictly positive integer")

        self.variable = variable  # deprecated
        self.reset = reset
        self.name_override = name_override
        self.backtrace = _tracer.trace_back(name)
        self.related = related

    def __setattr__(self, k, v):
        if k == "reset":
            v = wrap(v)
        _Value.__setattr__(self, k, v)

    def __repr__(self):
        return "<Signal " + (self.backtrace[-1][0] or "anonymous") + " at " + hex(id(self)) + ">"

    @classmethod
    def like(cls, other, **kwargs):
        """Create Signal based on another.

        Parameters
        ----------
        other : _Value
            Object to base this Signal on.

        See `migen.fhdl.bitcontainer.value_bits_sign` for details.
        """
        from migen.fhdl.bitcontainer import value_bits_sign
        return cls(bits_sign=value_bits_sign(other), **kwargs)

    def __hash__(self):
        return self.duid


class ClockSignal(_Value):
    """Clock signal for a given clock domain

    `ClockSignal` s for a given clock domain can be retrieved multiple
    times. They all ultimately refer to the same signal.

    Parameters
    ----------
    cd : str
        Clock domain to obtain a clock signal for. Defaults to `"sys"`.
    """
    def __init__(self, cd="sys"):
        _Value.__init__(self)
        self.cd = cd


class ResetSignal(_Value):
    """Reset signal for a given clock domain

    `ResetSignal` s for a given clock domain can be retrieved multiple
    times. They all ultimately refer to the same signal.

    Parameters
    ----------
    cd : str
        Clock domain to obtain a reset signal for. Defaults to `"sys"`.
    allow_reset_less : bool
        If the clock domain is resetless, return 0 instead of reporting an
        error.
    """
    def __init__(self, cd="sys", allow_reset_less=False):
        _Value.__init__(self)
        self.cd = cd
        self.allow_reset_less = allow_reset_less


# statements


class _Statement:
    pass


class _Assign(_Statement):
    def __init__(self, l, r):
        self.l = wrap(l)
        self.r = wrap(r)


def _check_statement(s):
    if isinstance(s, _collections.Iterable):
        return all(_check_statement(ss) for ss in s)
    else:
        return isinstance(s, _Statement)


class If(_Statement):
    """Conditional execution of statements

    Parameters
    ----------
    cond : _Value(1), in
        Condition
    *t : Statements
        Statements to execute if `cond` is asserted.

    Examples
    --------
    >>> a = Signal()
    >>> b = Signal()
    >>> c = Signal()
    >>> d = Signal()
    >>> If(a,
    ...     b.eq(1)
    ... ).Elif(c,
    ...     b.eq(0)
    ... ).Else(
    ...     b.eq(d)
    ... )
    """
    def __init__(self, cond, *t):
        if not _check_statement(t):
            raise TypeError("Not all test body objects are Migen statements")
        self.cond = wrap(cond)
        self.t = list(t)
        self.f = []

    def Else(self, *f):
        """Add an `else` conditional block

        Parameters
        ----------
        *f : Statements
            Statements to execute if all previous conditions fail.
        """
        if not _check_statement(f):
            raise TypeError("Not all test body objects are Migen statements")
        _insert_else(self, list(f))
        return self

    def Elif(self, cond, *t):
        """Add an `else if` conditional block

        Parameters
        ----------
        cond : _Value(1), in
            Condition
        *t : Statements
            Statements to execute if previous conditions fail and `cond`
            is asserted.
        """
        _insert_else(self, [If(cond, *t)])
        return self


def _insert_else(obj, clause):
    o = obj
    while o.f:
        assert(len(o.f) == 1)
        assert(isinstance(o.f[0], If))
        o = o.f[0]
    o.f = clause


class Case(_Statement):
    """Case/Switch statement

    Parameters
    ----------
    test : _Value, in
        Selector value used to decide which block to execute
    cases : dict
        Dictionary of cases. The keys are numeric constants to compare
        with `test`. The values are statements to be executed the
        corresponding key matches `test`. The dictionary may contain a
        string key `"default"` to mark a fall-through case that is
        executed if no other key matches.

    Examples
    --------
    >>> a = Signal()
    >>> b = Signal()
    >>> Case(a, {
    ...     0:         b.eq(1),
    ...     1:         b.eq(0),
    ...     "default": b.eq(0),
    ... })
    """
    def __init__(self, test, cases):
        self.test = wrap(test)
        self.cases = dict()
        for k, v in cases.items():
            if isinstance(k, (bool, int)):
                k = Constant(k)
            if (not isinstance(k, Constant) 
                    and not (isinstance(k, str) and k == "default")):
                raise TypeError("Case object is not a Migen constant")
            if not isinstance(v, _collections.Iterable):
                v = [v]
            if not _check_statement(v):
                raise TypeError("Not all objects for case {} "
                                "are Migen statements".format(k))
            self.cases[k] = v

    def makedefault(self, key=None):
        """Mark a key as the default case

        Deletes/substitutes any previously existing default case.

        Parameters
        ----------
        key : int or None
            Key to use as default case if no other key matches.
            By default, the largest key is the default key.
        """
        if key is None:
            for choice in self.cases.keys():
                if key is None or choice.value > key.value:
                    key = choice
        self.cases["default"] = self.cases[key]
        del self.cases[key]
        return self


# arrays


class _ArrayProxy(_Value):
    def __init__(self, choices, key):
        _Value.__init__(self)
        self.choices = []
        for c in choices:
            if isinstance(c, (bool, int)):
                c = Constant(c)
            if not isinstance(c, (_Value, Array)):
                raise TypeError("Array element is not a Migen value: {}"
                                .format(c))
            self.choices.append(c)
        self.key = key

    def __getattr__(self, attr):
        return _ArrayProxy([getattr(choice, attr) for choice in self.choices],
            self.key)

    def __getitem__(self, key):
        return _ArrayProxy([choice.__getitem__(key) for choice in self.choices],
            self.key)


class Array(list):
    """Addressable multiplexer

    An array is created from an iterable of values and indexed using the
    usual Python simple indexing notation (no negative indices or
    slices). It can be indexed by numeric constants, `_Value` s, or
    `Signal` s.

    The result of indexing the array is a proxy for the entry at the
    given index that can be used on either RHS or LHS of assignments.

    An array can be indexed multiple times.

    Multidimensional arrays are supported by packing inner arrays into
    outer arrays.

    Parameters
    ----------
    values : iterable of ints, _Values, Signals
        Entries of the array. Each entry can be a numeric constant, a
        `Signal` or a `Record`.

    Examples
    --------
    >>> a = Array(range(10))
    >>> b = Signal(max=10)
    >>> c = Signal(max=10)
    >>> b.eq(a[9 - c])
    """
    def __getitem__(self, key):
        if isinstance(key, Constant):
            return list.__getitem__(self, key.value)
        elif isinstance(key, _Value):
            return _ArrayProxy(self, key)
        else:
            return list.__getitem__(self, key)


class ClockDomain:
    """Synchronous domain

    Parameters
    ----------
    name : str or None
        Domain name. If None (the default) the name is inferred from the
        variable name this `ClockDomain` is assigned to (stripping any
        `"cd_"` prefix).
    reset_less : bool
        The domain does not use a reset signal. Registers within this
        domain are still all initialized to their reset state once, e.g.
        through Verilog `"initial"` statements.

    Attributes
    ----------
    clk : Signal, inout
        The clock for this domain. Can be driven or used to drive other
        signals (preferably in combinatorial context).
    rst : Signal or None, inout
        Reset signal for this domain. Can be driven or used to drive.
    """
    def __init__(self, name=None, reset_less=False):
        self.name = _tracer.get_obj_var_name(name)
        if self.name is None:
            raise ValueError("Cannot extract clock domain name from code, need to specify.")
        if self.name.startswith("cd_"):
            self.name = self.name[3:]
        if self.name[0].isdigit():
            raise ValueError("Clock domain name cannot start with a number.")
        self.clk = Signal(name_override=self.name + "_clk")
        if reset_less:
            self.rst = None
        else:
            self.rst = Signal(name_override=self.name + "_rst")

    def rename(self, new_name):
        """Rename the clock domain

        Parameters
        ----------
        new_name : str
            New name
        """
        self.name = new_name
        self.clk.name_override = new_name + "_clk"
        if self.rst is not None:
            self.rst.name_override = new_name + "_rst"


class _ClockDomainList(list):
    def __getitem__(self, key):
        if isinstance(key, str):
            for cd in self:
                if cd.name == key:
                    return cd
            raise KeyError(key)
        else:
            return list.__getitem__(self, key)


(SPECIAL_INPUT, SPECIAL_OUTPUT, SPECIAL_INOUT) = range(3)


class _Fragment:
    def __init__(self, comb=None, sync=None, specials=None, clock_domains=None):
        if comb is None: comb = []
        if sync is None: sync = dict()
        if specials is None: specials = set()
        if clock_domains is None: clock_domains = _ClockDomainList()

        self.comb = comb
        self.sync = sync
        self.specials = specials
        self.clock_domains = _ClockDomainList(clock_domains)

    def __add__(self, other):
        newsync = _collections.defaultdict(list)
        for k, v in self.sync.items():
            newsync[k] = v[:]
        for k, v in other.sync.items():
            newsync[k].extend(v)
        return _Fragment(self.comb + other.comb, newsync,
            self.specials | other.specials,
            self.clock_domains + other.clock_domains)

    def __iadd__(self, other):
        newsync = _collections.defaultdict(list)
        for k, v in self.sync.items():
            newsync[k] = v[:]
        for k, v in other.sync.items():
            newsync[k].extend(v)
        self.comb += other.comb
        self.sync = newsync
        self.specials |= other.specials
        self.clock_domains += other.clock_domains
        return self
