from litex.gen.fhdl.structure import *
from litex.gen.fhdl.specials import Memory, _MemoryPort, WRITE_FIRST, NO_CHANGE
from litex.gen.fhdl.decorators import ModuleTransformer
from litex.gen.util.misc import gcd_multiple
from litex.gen.fhdl.bitcontainer import log2_int


class FullMemoryWE(ModuleTransformer):
    def __init__(self):
        self.replacements = dict()

    def transform_fragment(self, i, f):
        newspecials = set()

        for orig in f.specials:
            if not isinstance(orig, Memory):
                newspecials.add(orig)
                continue
            global_granularity = gcd_multiple([p.we_granularity if p.we_granularity else orig.width for p in orig.ports])
            if global_granularity == orig.width:
                newspecials.add(orig)  # nothing to do
            else:
                newmems = []
                for i in range(orig.width//global_granularity):
                    if orig.init is None:
                        newinit = None
                    else:
                        newinit = [(v >> i*global_granularity) & (2**global_granularity - 1) for v in orig.init]
                    newmem = Memory(global_granularity, orig.depth, newinit, orig.name_override + "_grain" + str(i))
                    newspecials.add(newmem)
                    newmems.append(newmem)
                    for port in orig.ports:
                        port_granularity = port.we_granularity if port.we_granularity else orig.width
                        newport = _MemoryPort(
                            adr=port.adr,

                            dat_r=port.dat_r[i*global_granularity:(i+1)*global_granularity] if port.dat_r is not None else None,
                            we=port.we[i*global_granularity//port_granularity] if port.we is not None else None,
                            dat_w=port.dat_w[i*global_granularity:(i+1)*global_granularity] if port.dat_w is not None else None,

                            async_read=port.async_read,
                            re=port.re,
                            we_granularity=0,
                            mode=port.mode,
                            clock_domain=port.clock.cd)
                        newmem.ports.append(newport)
                        newspecials.add(newport)
                self.replacements[orig] = newmems

        f.specials = newspecials
        for oldmem in self.replacements.keys():
            f.specials -= set(oldmem.ports)


class MemoryToArray(ModuleTransformer):
    def __init__(self):
        self.replacements = dict()

    def transform_fragment(self, i, f):
        newspecials = set()
        processed_ports = set()

        for mem in f.specials:
            if not isinstance(mem, Memory):
                newspecials.add(mem)
                continue

            storage = Array()
            self.replacements[mem] = storage
            init = []
            if mem.init is not None:
                init = mem.init
            for d in init:
                mem_storage = Signal(mem.width, reset=d)
                storage.append(mem_storage)
            for _ in range(mem.depth-len(init)):
                mem_storage = Signal(mem.width)
                storage.append(mem_storage)

            for port in mem.ports:
                try:
                    sync = f.sync[port.clock.cd]
                except KeyError:
                    sync = f.sync[port.clock.cd] = []

                # read
                if port.async_read:
                    f.comb.append(port.dat_r.eq(storage[port.adr]))
                else:
                    if port.mode == WRITE_FIRST and port.we is not None:
                        adr_reg = Signal.like(port.adr)
                        rd_stmt = adr_reg.eq(port.adr)
                        f.comb.append(port.dat_r.eq(storage[adr_reg]))
                    elif port.mode == NO_CHANGE and port.we is not None:
                        rd_stmt = If(~port.we, port.dat_r.eq(storage[port.adr]))
                    else: # READ_FIRST or port.we is None, simplest case
                        rd_stmt = port.dat_r.eq(storage[port.adr])
                    if port.re is None:
                        sync.append(rd_stmt)
                    else:
                        sync.append(If(port.re, rd_stmt))

                # write
                if port.we is not None:
                    if port.we_granularity:
                        n = mem.width//port.we_granularity
                        for i in range(n):
                            m = i*port.we_granularity
                            M = (i+1)*port.we_granularity
                            sync.append(If(port.we[i],
                                        storage[port.adr][m:M].eq(port.dat_w[m:M])))
                    else:
                        sync.append(If(port.we,
                                       storage[port.adr].eq(port.dat_w)))

                processed_ports.add(port)

        newspecials -= processed_ports
        f.specials = newspecials


class SplitMemory(ModuleTransformer):
    """Split memories with depths that are not powers of two into smaller
    power-of-two memories.

    This prevents toolchains from rounding up and wasting resources."""

    def transform_fragment(self, i, f):
        old_specials, f.specials = f.specials, set()
        old_ports = set()

        for old in old_specials:
            if not isinstance(old, Memory):
                f.specials.add(old)
                continue
            try:
                log2_int(old.depth, need_pow2=True)
                f.specials.add(old)
            except ValueError:
                new, comb, sync = self._split_mem(old)
                old_ports |= set(old.ports)
                f.specials.update(new)
                f.comb += comb
                for cd, sy in sync.items():
                    s = f.sync.setdefault(cd, [])
                    s += sy
        f.specials -= old_ports

    def _split_mem(self, mem):
        depths = [1 << i for i in range(log2_int(mem.depth, need_pow2=False))
                  if mem.depth & (1 << i)]
        depths.reverse()
        inits = None
        if mem.init is not None:
            inits = list(mem.init)
        mems = []
        for i, depth in enumerate(depths):
            init = None
            if inits is not None:
                init = inits[:depth]
                del inits[:depth]
            name = "{}_part{}".format(mem.name_override, i)
            mems.append(Memory(width=mem.width, depth=depth,
                               init=init, name=name))
        ports = []
        comb = []
        sync = {}
        for port in mem.ports:
            p, c, s = self._split_port(port, mems)
            ports += p
            comb += c
            sy = sync.setdefault(port.clock.cd, [])
            sy += s
        return mems + ports, comb, sync

    def _split_port(self, port, mems):
        ports = [mem.get_port(write_capable=port.we is not None,
                              async_read=port.async_read,
                              has_re=port.re is not None,
                              we_granularity=port.we_granularity,
                              mode=port.mode,
                              clock_domain=port.clock.cd)
                 for mem in mems]

        sel = Signal(max=len(ports), reset=len(ports) - 1)
        sel_r = Signal.like(sel)
        eq = sel_r.eq(sel)
        if port.re is not None:
            eq = If(port.re, eq)
        comb, sync = [], []
        if port.async_read:
            comb += [eq]
        else:
            sync += [eq]
        comb += reversed([If(~port.adr[len(p.adr)], sel.eq(i))
                          for i, p in enumerate(ports)])
        comb += [p.adr.eq(port.adr) for p in ports]
        comb.append(port.dat_r.eq(Array([p.dat_r for p in ports])[sel_r]))
        if port.we is not None:
            comb.append(Array([p.we for p in ports])[sel].eq(port.we))
            comb += [p.dat_w.eq(port.dat_w) for p in ports]
        if port.re is not None:
            comb += [p.re.eq(port.re) for p in ports]
        return ports, comb, sync
