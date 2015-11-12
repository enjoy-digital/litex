from litex.gen.fhdl.structure import *
from litex.gen.fhdl.specials import Memory, _MemoryPort, WRITE_FIRST, NO_CHANGE
from litex.gen.fhdl.decorators import ModuleTransformer
from litex.gen.util.misc import gcd_multiple


class FullMemoryWE(ModuleTransformer):
    def __init__(self):
        self.replacments = dict()

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
                self.replacments[orig] = newmems

        f.specials = newspecials


class MemoryToArray(ModuleTransformer):
    def __init__(self):
        self.replacements = dict()

    def transform_fragment(self, i, f):
        newspecials = set()

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
                if port.we_granularity:
                    raise NotImplementedError
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
                                        storage[port.adr][m:M].eq(port.dat_w)))
                    else:
                        sync.append(If(port.we,
                                       storage[port.adr].eq(port.dat_w)))

        f.specials = newspecials
