from migen.util.misc import xdir
from migen.fhdl.std import *
from migen.fhdl.tracer import get_obj_var_name


class _CSRBase(HUID):
    def __init__(self, size, name):
        HUID.__init__(self)
        self.name = get_obj_var_name(name)
        if self.name is None:
            raise ValueError("Cannot extract CSR name from code, need to specify.")
        self.size = size


class CSR(_CSRBase):
    def __init__(self, size=1, name=None):
        _CSRBase.__init__(self, size, name)
        self.re = Signal(name=self.name + "_re")
        self.r = Signal(self.size, name=self.name + "_r")
        self.w = Signal(self.size, name=self.name + "_w")


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


class CSRStorage(_CompoundCSR):
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


def csrprefix(prefix, csrs, done):
    for csr in csrs:
        if csr.huid not in done:
            csr.name = prefix + csr.name
            done.add(csr.huid)


def memprefix(prefix, memories, done):
    for memory in memories:
        if memory.huid not in done:
            memory.name_override = prefix + memory.name_override
            done.add(memory.huid)


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
        return sorted(r, key=lambda x: x.huid)
    return gatherer


class AutoCSR:
    get_memories = _make_gatherer("get_memories", Memory, memprefix)
    get_csrs = _make_gatherer("get_csrs", _CSRBase, csrprefix)


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
