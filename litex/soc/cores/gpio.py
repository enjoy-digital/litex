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


class _GPIOIRQ:
    def add_irq(self, in_pads):
        self._rising_enable = CSRStorage(
            len(in_pads),
            description="GPIO IRQ Rising Edge Enable: 0: disabled, 1: enabled."
        )
        self._falling_enable = CSRStorage(
            len(in_pads),
            description="GPIO IRQ Falling Edge Enable: 0: disabled, 1: enabled."
        )

        # # #

        self.submodules.ev = EventManager()
        for n in range(len(in_pads)):
            esp = EventSourceProcess(name=f"i{n}", edge="both")
            self.comb += esp.trigger.eq(in_pads[n])
            self.comb += esp.rising_enable.eq(self._rising_enable.storage[n])
            self.comb += esp.falling_enable.eq(self._falling_enable.storage[n])
            setattr(self.ev, f"i{n}", esp)

# GPIO Input ---------------------------------------------------------------------------------------

class GPIOIn(_GPIOIRQ, Module, AutoCSR):
    def __init__(self, pads, with_irq=False):
        pads = _to_signal(pads)
        self._in = CSRStatus(len(pads), description="GPIO Input(s) Status.")
        self.specials += MultiReg(pads, self._in.status)
        if with_irq:
            self.add_irq(self._in.status)

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

class GPIOTristate(_GPIOIRQ, Module, AutoCSR):
    def __init__(self, pads, with_irq=False):
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

        if with_irq:
            self.add_irq(self._in.status)
