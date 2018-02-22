"""
Configuration and Status Registers
**********************************

The lowest-level description of a register is provided by the ``CSR`` class,
which maps to the value at a single address on the target bus. Also provided
are helper classes for dealing with values larger than the CSR buses data
width.

 * ``CSRConstant``, for constant values.
 * ``CSRStatus``, for providing information to the CPU.
 * ``CSRStorage``, for allowing control via the CPU.

Generating register banks
=========================
A module can provide bus-independent CSRs by implementing a ``get_csrs`` method
that returns a list of instances of the classes described above.

Similarly, bus-independent memories can be returned as a list by a
``get_memories`` method.

To avoid listing those manually, a module can inherit from the ``AutoCSR``
class, which provides ``get_csrs`` and ``get_memories`` methods that scan for
CSR and memory attributes and return their list.
"""

from litex.gen import *
from litex.gen.util.misc import xdir
from litex.gen.fhdl.tracer import get_obj_var_name


class _CSRBase(DUID):
    def __init__(self, size, name):
        DUID.__init__(self)
        self.name = get_obj_var_name(name)
        if self.name is None:
            raise ValueError("Cannot extract CSR name from code, need to specify.")
        self.size = size


class CSRConstant(DUID):
    """Register which contains a constant value.

    Useful for providing information on how a HDL was instantiated to firmware
    running on the device.
    """

    def __init__(self, value, bits_sign=None, name=None):
        DUID.__init__(self)
        self.value = Constant(value, bits_sign)
        self.name = get_obj_var_name(name)
        if self.name is None:
            raise ValueError("Cannot extract CSR name from code, need to specify.")

    def read(self):
        """Read method for simulation."""
        return self.value.value

    def __str__(self):
        return "<CSRConstant {}>".format(self.name)


class CSR(_CSRBase):
    """Basic CSR register.

    Parameters
    ----------
    size : int
        Size of the CSR register in bits.
        Must be less than CSR bus width!

    name : string
        Provide (or override the name) of the CSR register.

    Attributes
    ----------
    r : Signal(size), out
        Contains the data written from the bus interface.
        ``r`` is only valid when ``re`` is high.

    re : Signal(), out
        The strobe signal for ``r``.
        It is active for one cycle, after or during a write from the bus.

    w : Signal(size), in
        The value to be read from the bus.
        Must be provided at all times.
    """

    def __init__(self, size=1, name=None):
        _CSRBase.__init__(self, size, name)
        self.re = Signal(name=self.name + "_re")
        self.r = Signal(self.size, name=self.name + "_r")
        self.w = Signal(self.size, name=self.name + "_w")

    def read(self):
        """Read method for simulation."""
        return (yield self.w)

    def write(self, value):
        """Write method for simulation."""
        yield self.r.eq(value)
        yield self.re.eq(1)
        yield
        yield self.re.eq(0)

    def __str__(self):
        return "<CSR {}({})>".format(self.name, self.size)


class _CompoundCSR(_CSRBase, Module):
    def __init__(self, size, name):
        _CSRBase.__init__(self, size, name)
        self.simple_csrs = []

    def get_simple_csrs(self):
        if not self.finalized:
            raise FinalizeError
        return self.simple_csrs

    def do_finalize(self, busword):
        raise NotImplementedError


class CSRStatus(_CompoundCSR):
    """Status Register.

    The ``CSRStatus`` class is meant to be used as a status register that is
    read-only from the CPU.

    The user design is expected to drive its ``status`` signal.

    The advantage of using ``CSRStatus`` instead of using ``CSR`` and driving
    ``w`` is that the width of ``CSRStatus`` can be arbitrary.

    Status registers larger than the bus word width are automatically broken
    down into several ``CSR`` registers to span several addresses.

    *Be careful, though:* the atomicity of reads is not guaranteed.

    Parameters
    ----------
    size : int
        Size of the CSR register in bits.
        Can be bigger than the CSR bus width.

    reset : string
        Value of the register after reset.

    name : string
        Provide (or override the name) of the ``CSRStatus`` register.

    Attributes
    ----------
    status : Signal(size), in
        The value of the CSRStatus register.
    """

    def __init__(self, size=1, reset=0, name=None):
        _CompoundCSR.__init__(self, size, name)
        self.status = Signal(self.size, reset=reset)

    def do_finalize(self, busword):
        nwords = (self.size + busword - 1)//busword
        for i in reversed(range(nwords)):
            nbits = min(self.size - i*busword, busword)
            sc = CSR(nbits, self.name + str(i) if nwords > 1 else self.name)
            self.comb += sc.w.eq(self.status[i*busword:i*busword+nbits])
            self.simple_csrs.append(sc)

    def read(self):
        """Read method for simulation."""
        return (yield self.status)

    def __str__(self):
        return "<CSRStatus {}({})>".format(self.name, self.size)


class CSRStorage(_CompoundCSR):
    """Control Register.

    The ``CSRStorage`` class provides a memory location that can be read and
    written by the CPU, and read and optionally written by the design.

    It can span several CSR addresses.

    Parameters
    ----------
    size : int
        Size of the CSR register in bits.
        Can be bigger than the CSR bus width.

    reset : string
        Value of the register after reset.

    atomic_write : bool
        Provide an mechanism for atomic CPU writes is provided.
        When enabled, writes to the first CSR addresses go to a back-buffer
        whose contents are atomically copied to the main buffer when the last
        address is written.

    write_from_dev : bool
        Allow the design to update the CSRStorage value.
        *Warning*: The atomicity of reads by the CPU is not guaranteed.

    alignment_bits : int
        ???

    name : string
        Provide (or override the name) of the ``CSRStatus`` register.

    Attributes
    ----------
    storage_full : Signal(size), out
        ???

    storage : Signal(size), out
        Signal providing the value of the ``CSRStorage`` object.

    re : Signal(), in
        The strobe signal indicating a write to the ``CSRStorage`` register.
        It is active for one cycle, after or during a write from the bus.

    we : Signal(), out
        Only available when ``write_from_dev == True``
        ???

    dat_w : Signal(), out
        Only available when ``write_from_dev == True``
        ???
    """

    def __init__(self, size=1, reset=0, atomic_write=False, write_from_dev=False, alignment_bits=0, name=None):
        _CompoundCSR.__init__(self, size, name)
        self.alignment_bits = alignment_bits
        self.storage_full = Signal(self.size, reset=reset)
        self.storage = Signal(self.size - self.alignment_bits, reset=reset >> alignment_bits)
        self.comb += self.storage.eq(self.storage_full[self.alignment_bits:])
        self.atomic_write = atomic_write
        self.re = Signal()
        if write_from_dev:
            self.we = Signal()
            self.dat_w = Signal(self.size - self.alignment_bits)
            self.sync += If(self.we, self.storage_full.eq(self.dat_w << self.alignment_bits))

    def do_finalize(self, busword):
        nwords = (self.size + busword - 1)//busword
        if nwords > 1 and self.atomic_write:
            backstore = Signal(self.size - busword, name=self.name + "_backstore")
        for i in reversed(range(nwords)):
            nbits = min(self.size - i*busword, busword)
            sc = CSR(nbits, self.name + str(i) if nwords else self.name)
            self.simple_csrs.append(sc)
            lo = i*busword
            hi = lo+nbits
            # read
            if lo >= self.alignment_bits:
                self.comb += sc.w.eq(self.storage_full[lo:hi])
            elif hi > self.alignment_bits:
                self.comb += sc.w.eq(Cat(Replicate(0, hi - self.alignment_bits),
                    self.storage_full[self.alignment_bits:hi]))
            else:
                self.comb += sc.w.eq(0)
            # write
            if nwords > 1 and self.atomic_write:
                if i:
                    self.sync += If(sc.re, backstore[lo-busword:hi-busword].eq(sc.r))
                else:
                    self.sync += If(sc.re, self.storage_full.eq(Cat(sc.r, backstore)))
            else:
                self.sync += If(sc.re, self.storage_full[lo:hi].eq(sc.r))
        self.sync += self.re.eq(sc.re)

    def read(self):
        """Read method for simulation."""
        return (yield self.storage) << self.alignment_bits

    def write(self, value):
        """Write method for simulation."""
        yield self.storage.eq(value >> self.alignment_bits)
        yield self.re.eq(1)
        yield
        yield self.re.eq(0)

    def __str__(self):
        return "<CSRStorage {}({})>".format(self.name, self.size)


def csrprefix(prefix, csrs, done):
    for csr in csrs:
        if csr.duid not in done:
            csr.name = prefix + csr.name
            done.add(csr.duid)


def memprefix(prefix, memories, done):
    for memory in memories:
        if memory.duid not in done:
            memory.name_override = prefix + memory.name_override
            done.add(memory.duid)


def _make_gatherer(method, cls, prefix_cb):
    def gatherer(self):
        try:
            exclude = self.autocsr_exclude
        except AttributeError:
            exclude = {}
        try:
            prefixed = self.__prefixed
        except AttributeError:
            prefixed = self.__prefixed = set()
        r = []
        for k, v in xdir(self, True):
            if k not in exclude:
                if isinstance(v, cls):
                    r.append(v)
                elif hasattr(v, method) and callable(getattr(v, method)):
                    items = getattr(v, method)()
                    prefix_cb(k + "_", items, prefixed)
                    r += items
        return sorted(r, key=lambda x: x.duid)
    return gatherer


class AutoCSR:
    """MixIn to provide bus independent access to CSR registers.

    A module can inherit from the ``AutoCSR`` class, which provides
    ``get_csrs``, ``get_memories`` and ``get_constants`` methods that scan for
    CSR and memory attributes and return their list.

    If the module has child objects that implement ``get_csrs``,
    ``get_memories`` or ``get_constants``, they will be called by the
    ``AutoCSR`` methods and their CSR and memories added to the lists returned,
    with the child objects' names as prefixes.
    """
    get_memories = _make_gatherer("get_memories", Memory, memprefix)
    get_csrs = _make_gatherer("get_csrs", _CSRBase, csrprefix)
    get_constants = _make_gatherer("get_constants", CSRConstant, csrprefix)


class GenericBank(Module):
    def __init__(self, description, busword):
        # Turn description into simple CSRs and claim ownership of compound CSR modules
        self.simple_csrs = []
        for c in description:
            if isinstance(c, CSR):
                self.simple_csrs.append(c)
            else:
                c.finalize(busword)
                self.simple_csrs += c.get_simple_csrs()
                self.submodules += c
        self.decode_bits = bits_for(len(self.simple_csrs)-1)
