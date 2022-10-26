#
# This file is part of LiteX.
#
# Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2016-2019 Tim 'mithro' Ansell <me@mith.ro>
# Copyright (c) 2019 Sean Cross <sean@xobs.io>
# SPDX-License-Identifier: BSD-2-Clause


"""
Configuration and Status Registers
**********************************

The lowest-level description of a register is provided by the ``CSR`` class,
which maps to the value at a single address on the target bus. Also provided
are helper classes for dealing with values larger than the CSR buses data
width.

 * ``CSRConstant``, for constant values.
 * ``CSRStatus``,   for providing information to the CPU.
 * ``CSRStorage``,  for allowing control via the CPU.

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

from enum import IntEnum

from migen import *
from migen.util.misc import xdir
from migen.fhdl.tracer import get_obj_var_name

# CSRBase ------------------------------------------------------------------------------------------

class _CSRBase(DUID):
    def __init__(self, size, name, n=None):
        DUID.__init__(self)
        self.n     = n
        self.fixed = n is not None
        self.size = size
        self.name = get_obj_var_name(name)
        if self.name is None:
            raise ValueError("Cannot extract CSR name from code, need to specify.")
# CSRConstant --------------------------------------------------------------------------------------

class CSRConstant(DUID):
    """Register which contains a constant value.

    Useful for providing information on how a HDL was instantiated to firmware
    running on the device.
    """

    def __init__(self, value, bits_sign=None, name=None, n=None):
        DUID.__init__(self)
        self.n        = n
        self.fixed    = n is not None
        self.value    = Constant(value, bits_sign)
        self.name     = get_obj_var_name(name)
        self.constant = value
        if self.name is None:
            raise ValueError("Cannot extract CSR name from code, need to specify.")

    def read(self):
        """Read method for simulation."""
        yield
        return self.constant

# CSR ----------------------------------------------------------------------------------------------

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

    we : Signal(), out
        The strobe signal for ``w``.
        It is active for one cycle, after or during a read from the bus.
    """

    def __init__(self, size=1, name=None, n=None):
        _CSRBase.__init__(self, size, name, n)
        self.re = Signal(name=self.name + "_re")
        self.r  = Signal(self.size, name=self.name + "_r")
        self.we = Signal(name=self.name + "_we")
        self.w  = Signal(self.size, name=self.name + "_w")

    def read(self):
        """Read method for simulation."""
        yield self.we.eq(1)
        value = (yield self.w)
        yield
        yield self.we.eq(0)
        return value

    def write(self, value):
        """Write method for simulation."""
        yield self.r.eq(value)
        yield self.re.eq(1)
        yield
        yield self.re.eq(0)


class _CompoundCSR(_CSRBase, Module):
    def __init__(self, size, name, n=None):
        _CSRBase.__init__(self, size, name, n)
        self.simple_csrs = []

    def get_simple_csrs(self):
        if not self.finalized:
            raise FinalizeError
        return self.simple_csrs

    def do_finalize(self, busword):
        raise NotImplementedError

# CSRAccess ----------------------------------------------------------------------------------------

class CSRAccess(IntEnum):
    WriteOnly = 0
    ReadOnly  = 1
    ReadWrite = 2

# CSRField -----------------------------------------------------------------------------------------

class CSRField(Signal):
    """CSR Field.

    Parameters / Attributes
    -----------------------
    name : string
        Name of the CSR field.

    size : int
        Size of the CSR field in bits.

    offset : int (optional)
        Offset of the CSR field on the CSR register in bits.

    reset: int (optional)
        Reset value of the CSR field.

    description: string (optional)
        Description of the CSR Field (can be used to document the code and/or to be reused by tools
        to create the documentation).

    pulse: boolean (optional)
        Field value is only valid for one cycle when set to True. Only valid for 1-bit fields.

    access: enum (optional)
        Access type of the CSR field.

    values: list (optional)
        A list of supported values.
        If this is specified, a table will be generated containing the values in the specified order.
        The `value` must be an integer in order to allow for automatic constant generation in an IDE,
        except "do not care" bits are allowed.
        In the three-tuple variation, the middle value represents an enum value that can be displayed
        instead of the value.
                    [
                        ("0b0000", "disable the timer"),
                        ("0b0001", "slow", "slow timer"),
                        ("0b1xxx", "fast timer"),
                    ]
    """

    def __init__(self, name, size=1, offset=None, reset=0, description=None, pulse=False, access=None, values=None):
        assert access is None or (access in CSRAccess.__members__.values())
        self.name        = name
        self.size        = size
        self.offset      = offset
        self.reset_value = reset
        self.description = description
        self.access      = access
        self.pulse       = pulse
        self.values      = values
        Signal.__init__(self, size, name=name, reset=reset)


class CSRFieldAggregate:
    """CSR Field Aggregate."""

    def __init__(self, fields, access):
        self.check_names(fields)
        self.check_ordering_overlap(fields)
        self.fields = fields
        for field in fields:
            if field.access is None:
                field.access = access
            elif field.access == CSRAccess.ReadOnly:
                assert not field.pulse
                assert field.access == CSRAccess.ReadOnly
            elif field.access == CSRAccess.ReadWrite:
                assert field.access in [CSRAccess.ReadWrite, CSRAccess.WriteOnly]
                if field.pulse:
                    field.access = CSRAccess.WriteOnly
            setattr(self, field.name, field)

    @staticmethod
    def check_names(fields):
        names = []
        for field in fields:
            if field.name in names:
                raise ValueError("CSRField \"{}\" name is already used in CSR register".format(field.name))
            else:
                names.append(field.name)

    @staticmethod
    def check_ordering_overlap(fields):
        offset = 0
        for field in fields:
            if field.offset is not None:
                if field.offset < offset:
                    raise ValueError("CSRField ordering/overlap issue on \"{}\" field".format(field.name))
                offset = field.offset
            else:
                field.offset = offset
            offset += field.size

    def get_size(self):
        return self.fields[-1].offset + self.fields[-1].size

    def get_reset(self):
        reset = 0
        for field in self.fields:
            reset |= (field.reset_value << field.offset)
        return reset

# CSRStatus ----------------------------------------------------------------------------------------

class CSRStatus(_CompoundCSR):
    """Status Register.

    The ``CSRStatus`` class is meant to be used as a status register that is read-only from the CPU.

    The user design is expected to drive its ``status`` signal.

    The advantage of using ``CSRStatus`` instead of using ``CSR`` and driving ``w`` is that the
    width of ``CSRStatus`` can be arbitrary.

    Status registers larger than the bus word width are automatically broken down into several
    ``CSR`` registers to span several addresses.

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

    def __init__(self, size=1, reset=0, fields=[], name=None, description=None, read_only=True, n=None):
        if fields != []:
            self.fields = CSRFieldAggregate(fields, CSRAccess.ReadOnly)
            size  = self.fields.get_size()
            reset = self.fields.get_reset()
        _CompoundCSR.__init__(self, size, name, n)
        self.description = description
        self.read_only   = read_only
        self.status      = Signal(self.size, reset=reset)
        self.we          = Signal()
        self.re          = Signal()
        if not read_only:
            self.r       = Signal(self.size)
        for field in fields:
            self.comb += self.status[field.offset:field.offset + field.size].eq(getattr(self.fields, field.name))

    def do_finalize(self, busword, ordering):
        nwords = (self.size + busword - 1)//busword
        for i in reversed(range(nwords)) if ordering == "big" else range(nwords):
            nbits = min(self.size - i*busword, busword)
            sc    = CSR(nbits, self.name + str(i) if nwords > 1 else self.name)
            self.comb += sc.w.eq(self.status[i*busword:i*busword+nbits])
            self.simple_csrs.append(sc)
            if not self.read_only:
                lo = i*busword
                hi = lo+nbits
                self.sync += If(sc.re, self.r[lo:hi].eq(sc.r))
        self.comb += self.we.eq(sc.we)
        self.sync += self.re.eq(sc.re)

    def read(self):
        """Read method for simulation."""
        yield self.we.eq(1)
        value = (yield self.status)
        yield
        yield self.we.eq(0)
        return value

# CSRStorage ---------------------------------------------------------------------------------------

class CSRStorage(_CompoundCSR):
    """Control Register.

    The ``CSRStorage`` class provides a memory location that can be read and written by the CPU, and read and optionally written by the design.

    It can span several CSR addresses.

    Parameters
    ----------
    size : int
        Size of the CSR register in bits. Can be bigger than the CSR bus width.

    reset : string
        Value of the register after reset.

    reset_less : bool
        If `True`, do not generate reset logic for CSRStorage.

    atomic_write : bool
        Provide an mechanism for atomic CPU writes is provided. When enabled, writes to the first
        CSR addresses go to a back-buffer whose contents are atomically copied to the main buffer
        when the last address is written.

    write_from_dev : bool
        Allow the design to update the CSRStorage value. *Warning*: The atomicity of reads by the
         CPU is not guaranteed.

    name : string
        Provide (or override the name) of the ``CSRStatus`` register.

    Attributes
    ----------
    storage : Signal(size), out
        Signal providing the value of the ``CSRStorage`` object.

    re : Signal(), in
        The strobe signal indicating a write to the ``CSRStorage`` register from the CPU. It is active
        for one cycle, after or during a write from the bus.

    we : Signal(), out
        The strobe signal to write to the ``CSRStorage`` register from the logic. Only available when
        ``write_from_dev == True``


    dat_w : Signal(), out
        The write data to write to the ``CSRStorage`` register from the logic. Only available when
        ``write_from_dev == True``
    """

    def __init__(self, size=1, reset=0, reset_less=False, fields=[], atomic_write=False, write_from_dev=False, name=None, description=None, n=None):
        if fields != []:
            self.fields = CSRFieldAggregate(fields, CSRAccess.ReadWrite)
            size  = self.fields.get_size()
            reset = self.fields.get_reset()
        _CompoundCSR.__init__(self, size, name, n)
        self.description  = description
        self.storage      = Signal(self.size, reset=reset, reset_less=reset_less)
        self.atomic_write = atomic_write
        self.re           = Signal()
        if write_from_dev:
            self.we    = Signal()
            self.dat_w = Signal(self.size)
            self.sync += If(self.we, self.storage.eq(self.dat_w))
        for field in [*fields]:
            field_assign = getattr(self.fields, field.name).eq(self.storage[field.offset:field.offset + field.size])
            if field.pulse:
                self.comb += If(self.re, field_assign)
            else:
                self.comb += field_assign

    def do_finalize(self, busword, ordering):
        nwords = (self.size + busword - 1)//busword
        if nwords > 1 and self.atomic_write:
            backstore = Signal(self.size - busword, name=self.name + "_backstore")
        for i in reversed(range(nwords)) if ordering == "big" else range(nwords):
            nbits = min(self.size - i*busword, busword)
            sc    = CSR(nbits, self.name + str(i) if nwords else self.name)
            self.simple_csrs.append(sc)
            lo = i*busword
            hi = lo+nbits
            # read
            self.comb += sc.w.eq(self.storage[lo:hi])
            # write
            if nwords > 1 and self.atomic_write:
                if i:
                    self.sync += If(sc.re, backstore[lo-busword:hi-busword].eq(sc.r))
                else:
                    self.sync += If(sc.re, self.storage.eq(Cat(sc.r, backstore)))
            else:
                self.sync += If(sc.re, self.storage[lo:hi].eq(sc.r))
        self.sync += self.re.eq(sc.re)

    def read(self):
        """Read method for simulation.

        Side effects: none (asynchronous)."""
        return (yield self.storage)

    def write(self, value):
        """Write method for simulation.

        Side effects: synchronous advances simulation clk by one tick."""
        if bits_for(value) > self.size:
            raise ValueError(f"value {value} exceeds range of {self.size} bit CSR {self.name}.")

        yield self.storage.eq(value)
        yield self.re.eq(1)
        if hasattr(self, "fields"):
            for field in [*self.fields.fields]:
                yield getattr(self.fields, field.name).eq((value >> field.offset) & (2**field.size -1))
        yield
        yield self.re.eq(0)
        if hasattr(self, "fields"):
            for field in [*self.fields.fields]:
                if field.pulse:
                    yield getattr(self.fields, field.name).eq(0)

# AutoCSR & Helpers --------------------------------------------------------------------------------

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

def _sort_gathered_items(items):

    # Create list of variable items and sort it by DUID.
    # --------------------------------------------------
    variable_items = []
    for item in items:
        if not item.fixed:
            variable_items.append(item)
    variable_items = sorted(variable_items, key=lambda x: x.duid)

    # Create list of fixed items:
    # ---------------------------
    fixed_items = []
    for item in items:
        if item.fixed:
            fixed_items.append(item)

    # Determine items length.
    # -----------------------
    # Set to length of provided items.
    items_length = len(items)

    # Eventually extend with fixed items:
    for item in fixed_items:
        if item.n > items_length:
            items_length = (item.n + 1)

    # Create list of sorted items:
    # ----------------------------

    # Create empty list.
    sorted_items = [None for _ in range(items_length)]

    # Fill fixed items.
    for item in fixed_items:
        if sorted_items[item.n] is not None:
            csr0 = item.name
            csr1 = sorted_items[item.n].name
            raise ValueError(f"CSR conflict on location {item.n} between {csr0} and {csr1}.")
        sorted_items[item.n] = item

    # Fill variable items in empty locations.
    while len(variable_items):
        item = variable_items.pop(0)
        for i in range(items_length):
            if sorted_items[i] is None:
                sorted_items[i] = item
                break

    # Fill remaining location with reserved CSR.
    for i in range(items_length):
        if sorted_items[i] is None:
            sorted_items[i] = CSR(name=f"reserved{i}")


    # Verify all locations are filled.
    assert None not in sorted_items

    # Return.
    return sorted_items

def _make_gatherer(method, cls, prefix_cb):
    def gatherer(self, sort=False):
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
        r = sorted(r, key=lambda x: x.duid)
        if sort:
            r = _sort_gathered_items(r)
        return r
    return gatherer


class AutoCSR:
    """MixIn to provide bus independent access to CSR registers.

    A module can inherit from the ``AutoCSR`` class, which provides ``get_csrs``, ``get_memories``
    and ``get_constants`` methods that scan for CSR and memory attributes and return their list.

    If the module has child objects that implement ``get_csrs``, ``get_memories`` or ``get_constants``,
    they will be called by the``AutoCSR`` methods and their CSR and memories added to the lists returned,
    with the child objects' names as prefixes.
    """
    get_memories  = _make_gatherer(method="get_memories",  cls=Memory,      prefix_cb=memprefix)
    get_csrs      = _make_gatherer(method="get_csrs",      cls=_CSRBase,    prefix_cb=csrprefix)
    get_constants = _make_gatherer(method="get_constants", cls=CSRConstant, prefix_cb=csrprefix)


class GenericBank(Module):
    def __init__(self, description, busword, ordering="big"):
        assert ordering in ["big", "little"]
        # Turn description into simple CSRs and claim ownership of compound CSR modules
        self.simple_csrs = []
        for c in description:
            if isinstance(c, CSR):
                assert c.size <= busword
                self.simple_csrs.append(c)
            elif hasattr(c, "finalize"):
                c.finalize(busword, ordering)
                self.simple_csrs += c.get_simple_csrs()
                self.submodules  += c
