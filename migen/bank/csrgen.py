from migen.util.misc import xdir
from migen.fhdl.std import *
from migen.bus import csr
from migen.bank.bank import GenericBank

class Bank(GenericBank):
    def __init__(self, description, address=0, bus=None):
        if bus is None:
            bus = csr.Interface()
        self.bus = bus

        ###

        GenericBank.__init__(self, description, flen(self.bus.dat_w))

        sel = Signal()
        self.comb += sel.eq(self.bus.adr[9:] == address)

        for i, c in enumerate(self.simple_csrs):
            self.comb += [
                c.r.eq(self.bus.dat_w[:c.size]),
                c.re.eq(sel & \
                    self.bus.we & \
                    (self.bus.adr[:self.decode_bits] == i))
            ]

        brcases = dict((i, self.bus.dat_r.eq(c.w)) for i, c in enumerate(self.simple_csrs))
        self.sync += [
            self.bus.dat_r.eq(0),
            If(sel, Case(self.bus.adr[:self.decode_bits], brcases))
        ]

# address_map(name, memory) returns the CSR offset at which to map
# the CSR object (register bank or memory).
# If memory=None, the object is the register bank of object source.name.
# Otherwise, it is a memory object belonging to source.name.
# address_map is called exactly once for each object at each call to
# scan(), so it can have side effects.
class BankArray(Module):
    def __init__(self, source, address_map, *ifargs, **ifkwargs):
        self.source = source
        self.address_map = address_map
        self.scan(ifargs, ifkwargs)

    def scan(self, ifargs, ifkwargs):
        self.banks = []
        self.srams = []
        for name, obj in xdir(self.source, True):
            if hasattr(obj, "get_csrs"):
                csrs = obj.get_csrs()
            else:
                csrs = []
            if hasattr(obj, "get_memories"):
                memories = obj.get_memories()
                for memory in memories:
                    mapaddr = self.address_map(name, memory)
                    if mapaddr is None:
                        continue
                    sram_bus = csr.Interface(*ifargs, **ifkwargs)
                    mmap = csr.SRAM(memory, mapaddr, bus=sram_bus)
                    self.submodules += mmap
                    csrs += mmap.get_csrs()
                    self.srams.append((name, memory, mapaddr, mmap))
            if csrs:
                mapaddr = self.address_map(name, None)
                if mapaddr is None:
                    continue
                bank_bus = csr.Interface(*ifargs, **ifkwargs)
                rmap = Bank(csrs, mapaddr, bus=bank_bus)
                self.submodules += rmap
                self.banks.append((name, csrs, mapaddr, rmap))

    def get_rmaps(self):
        return [rmap for name, csrs, mapaddr, rmap in self.banks]

    def get_mmaps(self):
        return [mmap for name, memory, mapaddr, mmap in self.srams]

    def get_buses(self):
        return [i.bus for i in self.get_rmaps() + self.get_mmaps()]
