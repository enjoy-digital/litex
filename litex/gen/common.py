#
# This file is part of LiteX.
#
# This file is Copyright (c) 2018-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.fhdl.module import _ModuleProxy
from migen.fhdl.specials import Special

from litex.soc.interconnect.csr import AutoCSR
from litex.soc.integration.doc import AutoDoc


# Bit/Bytes Reversing ------------------------------------------------------------------------------

def reverse_bits(s):
    return s[::-1]


def reverse_bytes(s):
    n = (len(s) + 7)//8
    return Cat(*[s[i*8:min((i + 1)*8, len(s))]
        for i in reversed(range(n))])

# LiteX Module -------------------------------------------------------------------------------------

class LiteXModule(Module, AutoCSR, AutoDoc):
    def __setattr__(m, name, value):
        # Migen:
        if name in ["comb", "sync", "specials", "submodules", "clock_domains"]:
            if not isinstance(value, _ModuleProxy):
                raise AttributeError("Attempted to assign special Module property - use += instead")
        # LiteX fix-up: Automatically collect specials/submodules/clock_domains:
        # - m.module_x  = .. equivalent of Migen's m.submodules.module_x = ..
        elif isinstance(value, Module)      and ((name, value) not in m._submodules):
            setattr(m.submodules, name, value)
        # - m.special_x = .. equivalent of Migen's m.specials.special_x  = ..
        elif isinstance(value, Special)     and (value not in m._fragment.specials):
            setattr(m.specials, name, value)
        # - m.cd_x      = .. equivalent of Migen's m.clock_domains.cd_x  = ..
        elif isinstance(value, ClockDomain) and (value not in m._fragment.clock_domains):
            setattr(m.clock_domains, name, value)
        # Else use default __setattr__.
        else:
            object.__setattr__(m, name, value)

    # LiteX fix-up: Automatically collect specials/submodules/clock_domains:
    def __iadd__(m, other):
        # - m += module_x  equivalent of Migen's m.submodules += module_x.
        if isinstance(other, Module):
            print(other)
            m.submodules += other
        # - m += special_x  equivalent of Migen's m.specials += special_x.
        elif isinstnace(other, Special):
            m.specials += other
        # - m += cd_x  equivalent of Migen's m.clock_domains += cd_x.
        elif isinstance(other, ClockDomain):
            m.clock_domains += other
        # Else use default __iadd__.
        else:
            object.__iadd__(m, other)
        return m
