#
# This file is part of LiteX.
#
# Copyright (c) 2013-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2019-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import MultiReg

from litex.soc.interconnect.csr import *

from litex.soc.interconnect.csr_eventmanager import *

# Helpers ------------------------------------------------------------------------------------------

def _to_signal(obj):
    return obj.raw_bits() if isinstance(obj, Record) else obj

# GPIO Input ---------------------------------------------------------------------------------------

class GPIOIn(Module, AutoCSR):
    """GPIO Input

    Provides a GPIO Input peripheral. An optional IRQ dict can be passed to add rising or falling
    interrupts to pads.

    Ex: pads=Signal(8), irqs={}                    : 8-bit Input, No IRQ.
        pads=Signal(8), irqs={0: "rise", 7: "fall"}: 8-bit Input, rising IRQ on 0, falling IRQ on 1.
    """
    def __init__(self, pads, irqs={}):
        pads = _to_signal(pads)

        # Inputs
        self._in = CSRStatus(len(pads), description="GPIO Input(s) Status.")
        self.specials += MultiReg(pads, self._in.status)

        # IRQs
        if len(irqs):
            self.submodules.ev = EventManager()
            for n, irq_type in irqs.items():
                assert irq_type in ["fall", "falling", "rise", "rising"]
                assert len(pads) > n
                name = f"i{n}"
                if irq_type in ["rise", "rising"]:
                    setattr(self.ev, f"i{n}", EventSourcePulse())
                if irq_type in ["fall", "falling"]:
                    setattr(self.ev, f"i{n}", EventSourceProcess())
                self.comb += getattr(self.ev, f"i{n}").trigger.eq(pads[n])

# GPIO Output --------------------------------------------------------------------------------------

class GPIOOut(Module, AutoCSR):
    def __init__(self, pads):
        pads = _to_signal(pads)
        self.out = CSRStorage(len(pads), description="GPIO Output(s) Control.")
        self.comb += pads.eq(self.out.storage)

# GPIO Input/Output --------------------------------------------------------------------------------

class GPIOInOut(Module):
    def __init__(self, in_pads, out_pads):
        self.submodules.gpio_in  = GPIOIn(in_pads)
        self.submodules.gpio_out = GPIOOut(out_pads)

    def get_csrs(self):
        return self.gpio_in.get_csrs() + self.gpio_out.get_csrs()

# GPIO Tristate ------------------------------------------------------------------------------------

class GPIOTristate(Module, AutoCSR):
    def __init__(self, pads):
        assert isinstance(pads, Signal)
        nbits     = len(pads)
        self._oe  = CSRStorage(nbits, description="GPIO Tristate(s) Control.")
        self._in  = CSRStatus(nbits,  description="GPIO Input(s) Status.")
        self._out = CSRStorage(nbits, description="GPIO Ouptut(s) Control.")

        # # #

        for i in range(nbits):
            t = TSTriple()
            self.specials += t.get_tristate(pads[i])
            self.comb += t.oe.eq(self._oe.storage[i])
            self.comb += t.o.eq(self._out.storage[i])
            self.specials += MultiReg(t.i, self._in.status[i])
