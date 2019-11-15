# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2016-2019 Tim 'mithro' Ansell <me@mith.ro>
# License: BSD

"""
CSR-2 bus
=========

The CSR-2 bus is a low-bandwidth, resource-sensitive bus designed for accessing
the configuration and status registers of cores from software.
"""

from functools import reduce
from operator import or_

from migen import *
from migen.genlib.record import *
from migen.genlib.misc import chooser
from migen.util.misc import xdir

from litex.soc.interconnect import csr
from litex.soc.interconnect.csr import CSRStorage


_layout = [
    ("adr",  "address_width", DIR_M_TO_S),
    ("we",                 1, DIR_M_TO_S),
    ("dat_w",   "data_width", DIR_M_TO_S),
    ("dat_r",   "data_width", DIR_S_TO_M)
]


class Interface(Record):
    def __init__(self, data_width=8, address_width=14, alignment=32):
        self.alignment = alignment
        Record.__init__(self, set_layout_parameters(_layout,
            data_width=data_width, address_width=address_width))

    @classmethod
    def like(self, other):
        return Interface(len(other.dat_w),
                         len(other.adr))

    def write(self, adr, dat):
        yield self.adr.eq(adr)
        yield self.dat_w.eq(dat)
        yield self.we.eq(1)
        yield
        yield self.we.eq(0)

    def read(self, adr):
        yield self.adr.eq(adr)
        yield
        yield
        return (yield self.dat_r)


class Interconnect(Module):
    def __init__(self, master, slaves):
        self.comb += master.connect(*slaves)


class InterconnectShared(Module):
    def __init__(self, masters, slaves):
        intermediate = Interface.like(masters[0])
        self.comb += [
            intermediate.adr.eq(reduce(or_, [masters[i].adr for i in range(len(masters))])),
            intermediate.we.eq(reduce(or_, [masters[i].we for i in range(len(masters))])),
            intermediate.dat_w.eq(reduce(or_, [masters[i].dat_w for i in range(len(masters))]))
        ]
        for i in range(len(masters)):
            self.comb += masters[i].dat_r.eq(intermediate.dat_r)
        self.comb += intermediate.connect(*slaves)


class SRAM(Module):
    def __init__(self, mem_or_size, address, read_only=None, init=None, bus=None):
        if bus is None:
            bus = Interface()
        self.bus = bus
        data_width = len(self.bus.dat_w)
        if isinstance(mem_or_size, Memory):
            mem = mem_or_size
        else:
            mem = Memory(data_width, mem_or_size//(data_width//8), init=init)
        mem_size = int(mem.width*mem.depth/8)
        if mem_size > 512:
            print("WARNING: memory > 512 bytes in CSR region requires paged access".format(mem_size))
        csrw_per_memw = (mem.width + data_width - 1)//data_width
        word_bits = log2_int(csrw_per_memw)
        page_bits = log2_int((mem.depth*csrw_per_memw + 511)//512, False)
        if page_bits:
            self._page = CSRStorage(page_bits, name=mem.name_override + "_page")
        else:
            self._page = None
        if read_only is None:
            if hasattr(mem, "bus_read_only"):
                read_only = mem.bus_read_only
            else:
                read_only = False

        ###

        port = mem.get_port(write_capable=not read_only)
        self.specials += mem, port

        sel = Signal()
        sel_r = Signal()
        self.sync += sel_r.eq(sel)
        self.comb += sel.eq(self.bus.adr[9:] == address)

        if word_bits:
            word_index = Signal(word_bits)
            word_expanded = Signal(csrw_per_memw*data_width)
            self.sync += word_index.eq(self.bus.adr[:word_bits])
            self.comb += [
                word_expanded.eq(port.dat_r),
                If(sel_r,
                    chooser(word_expanded, word_index, self.bus.dat_r, n=csrw_per_memw, reverse=True)
                )
            ]
            if not read_only:
                wregs = []
                for i in range(csrw_per_memw-1):
                    wreg = Signal(data_width)
                    self.sync += If(sel & self.bus.we & (self.bus.adr[:word_bits] == i), wreg.eq(self.bus.dat_w))
                    wregs.append(wreg)
                memword_chunks = [self.bus.dat_w] + list(reversed(wregs))
                self.comb += [
                    port.we.eq(sel & self.bus.we & (self.bus.adr[:word_bits] == csrw_per_memw - 1)),
                    port.dat_w.eq(Cat(*memword_chunks))
                ]
        else:
            self.comb += If(sel_r, self.bus.dat_r.eq(port.dat_r))
            if not read_only:
                self.comb += [
                    port.we.eq(sel & self.bus.we),
                    port.dat_w.eq(self.bus.dat_w)
                ]

        if self._page is None:
            self.comb += port.adr.eq(self.bus.adr[word_bits:word_bits+len(port.adr)])
        else:
            pv = self._page.storage
            self.comb += port.adr.eq(Cat(self.bus.adr[word_bits:word_bits+len(port.adr)-len(pv)], pv))

    def get_csrs(self):
        if self._page is None:
            return []
        else:
            return [self._page]


class CSRBank(csr.GenericBank):
    def __init__(self, description, address=0, bus=None):
        if bus is None:
            bus = Interface()
        self.bus = bus

        ###

        csr.GenericBank.__init__(self, description, len(self.bus.dat_w))

        sel = Signal()
        self.comb += sel.eq(self.bus.adr[9:] == address)
        if bus.alignment == 64:
            self.comb += If(self.bus.adr[0], sel.eq(0))

        adr_shift = log2_int(bus.alignment//32)

        for i, c in enumerate(self.simple_csrs):
            self.comb += [
                c.r.eq(self.bus.dat_w[:c.size]),
                c.re.eq(sel & \
                    self.bus.we & \
                    (self.bus.adr[adr_shift:adr_shift+self.decode_bits] == i)),
                c.we.eq(sel & \
                    ~self.bus.we & \
                    (self.bus.adr[adr_shift:adr_shift+self.decode_bits] == i)),
            ]

        brcases = dict((i, self.bus.dat_r.eq(c.w)) for i, c in enumerate(self.simple_csrs))
        self.sync += [
            self.bus.dat_r.eq(0),
            If(sel, Case(self.bus.adr[adr_shift:adr_shift+self.decode_bits], brcases))
        ]


# address_map(name, memory) returns the CSR offset at which to map
# the CSR object (register bank or memory).
# If memory=None, the object is the register bank of object source.name.
# Otherwise, it is a memory object belonging to source.name.
# address_map is called exactly once for each object at each call to
# scan(), so it can have side effects.
class CSRBankArray(Module):
    def __init__(self, source, address_map, *ifargs, **ifkwargs):
        self.source = source
        self.address_map = address_map
        self.scan(ifargs, ifkwargs)

    def scan(self, ifargs, ifkwargs):
        self.banks = []
        self.srams = []
        self.constants = []
        for name, obj in xdir(self.source, True):
            if hasattr(obj, "get_csrs"):
                csrs = obj.get_csrs()
            else:
                csrs = []
            if hasattr(obj, "get_memories"):
                memories = obj.get_memories()
                for memory in memories:
                    if isinstance(memory, tuple):
                        read_only, memory = memory
                    else:
                        read_only = False
                    mapaddr = self.address_map(name, memory)
                    if mapaddr is None:
                        continue
                    sram_bus = Interface(*ifargs, **ifkwargs)
                    mmap = SRAM(memory, mapaddr, read_only=read_only,
                                bus=sram_bus)
                    self.submodules += mmap
                    csrs += mmap.get_csrs()
                    self.srams.append((name, memory, mapaddr, mmap))
            if hasattr(obj, "get_constants"):
                for constant in obj.get_constants():
                    self.constants.append((name, constant))
            if csrs:
                mapaddr = self.address_map(name, None)
                if mapaddr is None:
                    continue
                bank_bus = Interface(*ifargs, **ifkwargs)
                rmap = CSRBank(csrs, mapaddr, bus=bank_bus)
                self.submodules += rmap
                self.banks.append((name, csrs, mapaddr, rmap))

    def get_rmaps(self):
        return [rmap for name, csrs, mapaddr, rmap in self.banks]

    def get_mmaps(self):
        return [mmap for name, memory, mapaddr, mmap in self.srams]

    def get_buses(self):
        return [i.bus for i in self.get_rmaps() + self.get_mmaps()]
