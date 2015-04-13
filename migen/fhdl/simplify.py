from migen.fhdl.std import *
from migen.fhdl.specials import _MemoryPort
from migen.fhdl.decorators import ModuleTransformer
from migen.util.misc import gcd_multiple


class FullMemoryWE(ModuleTransformer):
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
                for i in range(orig.width//global_granularity):
                    if orig.init is None:
                        newinit = None
                    else:
                        newinit = [(v >> i*global_granularity) & (2**global_granularity - 1) for v in orig.init]
                    newmem = Memory(global_granularity, orig.depth, newinit, orig.name_override + "_grain" + str(i))
                    newspecials.add(newmem)
                    for port in orig.ports:
                        port_granularity = port.we_granularity if port.we_granularity else orig.width
                        newport = _MemoryPort(adr=port.adr,

                            dat_r=port.dat_r[i*global_granularity:(i+1)*global_granularity] if port.dat_r is not None else None,
                            we=port.we[i*global_granularity//port_granularity] if port.we is not None else None,
                            dat_w=port.dat_w[i*global_granularity:(i+1)*global_granularity] if port.dat_w is not None else None,

                              async_read=port.async_read,
                              re=port.re,
                              we_granularity=0,
                              mode=port.mode,
                              clock_domain=port.clock)
                        newmem.ports.append(newport)
                        newspecials.add(newport)

        f.specials = newspecials
