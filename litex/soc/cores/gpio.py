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

from enum import Enum

# Helpers ------------------------------------------------------------------------------------------

def _to_signal(obj):
    return obj.raw_bits() if isinstance(obj, Record) else obj

class IRQ_Type(Enum):
    NO_IRQ = 0
    RISING_EDGE = 1
    FALLING_EDGE = 2

# GPIO Input ---------------------------------------------------------------------------------------

class GPIOIn(Module, AutoCSR):
    """GPIO Input

    Parameters / Attributes
    -----------------------
    pads : Object
        GPIO Input pads description.

    irq : list of IRQ_Type (optional)
        List containing IRQ types for each pad. It can take values supported by IRQ_Type Enum.

        Example use:
        irq = [IRQ_Type.NO_IRQ, IRQ_Type.NO_IRQ, IRQ_Type.FALLING_EDGE, IRQ_Type.RISING_EDGE] 
        This adds interrupts on pins 2 (falling edge) and 3 (rising edge).
    """
    def __init__(self, pads, irq=None):
        pads = _to_signal(pads)
        self._in = CSRStatus(len(pads), description="GPIO Input(s) Status.")
        self.specials += MultiReg(pads, self._in.status)
        
        if irq:
            assert(len(irq) <= len(pads))
            self.submodules.ev = EventManager()

            irq_no = []
            for i, irq_type in enumerate(irq):
                assert(irq_type, IRQ_Type)
                name = "pin" + str(i)
                if irq_type == IRQ_Type.RISING_EDGE:
                    setattr(self.ev, name, EventSourcePulse())
                    irq_no.append(i)
                elif irq_type == IRQ_Type.FALLING_EDGE:
                    setattr(self.ev, name, EventSourceProcess())
                    irq_no.append(i)
                
            self.ev.finalize()

            sources_u = [v for k, v in xdir(self.ev, True) if isinstance(v, (EventSourcePulse, EventSourceProcess))]
            for i, source in enumerate(sources_u):
                self.comb += source.trigger.eq(pads[irq_no[i]])

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
