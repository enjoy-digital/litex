#
# This file is part of LiteX.
#
# Copyright (c) 2013-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2019-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import MultiReg

from litex.gen import *
from litex.build.io import SDRTristate

from litex.soc.interconnect.csr import *
from litex.soc.interconnect.csr_eventmanager import *

# Helpers ------------------------------------------------------------------------------------------

def _to_signal(obj):
    return obj.raw_bits() if isinstance(obj, Record) else obj


class _GPIOIRQ(LiteXModule):
    def add_irq(self, in_pads):
        self._mode = CSRStorage(len(in_pads), description="GPIO IRQ Mode: 0: Edge, 1: Change.")
        self._edge = CSRStorage(len(in_pads), description="GPIO IRQ Edge (when in Edge mode): 0: Rising Edge, 1: Falling Edge.")

        # # #

        self.ev = EventManager()

        in_pads_n_d = Signal(len(in_pads))
        self.sync += in_pads_n_d.eq(in_pads)

        for n in range(len(in_pads)):
            esp = EventSourcePulse(name=f"i{n}")
            self.comb += [
                # Change mode.
                If(self._mode.storage[n],
                    esp.trigger.eq(in_pads[n] ^ in_pads_n_d[n])
                # Falling edge.
                ).Elif(self._edge.storage[n],
                    esp.trigger.eq(~in_pads[n] & in_pads_n_d[n])
                # Rising edge.
                ).Else(
                    esp.trigger.eq(in_pads[n] & ~in_pads_n_d[n])
                )
            ]
            setattr(self.ev, f"i{n}", esp)
        self.ev.finalize()

# GPIO Input ---------------------------------------------------------------------------------------

class GPIOIn(_GPIOIRQ):
    def __init__(self, pads, with_irq=False):
        pads = _to_signal(pads)
        self._in = CSRStatus(len(pads), description="GPIO Input(s) Status.")
        self.specials += MultiReg(pads, self._in.status)
        if with_irq:
            self.add_irq(self._in.status)

# GPIO Output --------------------------------------------------------------------------------------

class GPIOOut(LiteXModule):
    def __init__(self, pads, reset=0):
        pads = _to_signal(pads)
        self.out = CSRStorage(len(pads), reset=reset, description="GPIO Output(s) Control.")
        self.comb += pads.eq(self.out.storage)

# GPIO Input/Output --------------------------------------------------------------------------------

class GPIOInOut(LiteXModule):
    def __init__(self, in_pads, out_pads):
        self.gpio_in  = GPIOIn(in_pads)
        self.gpio_out = GPIOOut(out_pads)

    def get_csrs(self):
        return self.gpio_in.get_csrs() + self.gpio_out.get_csrs()

# GPIO Tristate ------------------------------------------------------------------------------------

class GPIOTristate(_GPIOIRQ):
    def __init__(self, pads, with_irq=False):
        internal = not (hasattr(pads, "o") and hasattr(pads, "oe") and hasattr(pads, "i"))
        nbits    = len(pads) if internal else len(pads.o)

        self._oe  = CSRStorage(nbits, description="GPIO Tristate(s) Control.")
        self._in  = CSRStatus(nbits,  description="GPIO Input(s) Status.")
        self._out = CSRStorage(nbits, description="GPIO Ouptut(s) Control.")

        # # #

        # Internal Tristate.
        if internal:
            if isinstance(pads, Record):
                pads = pads.flatten()
            if isinstance(pads, list):
                start = 0
                for pad in pads:
                    _out = self._out.storage[start:start+len(pad)]
                    _oe  = self._oe.storage[start:start+len(pad)]
                    _in  = self._in.status[start:start+len(pad)]

                    self.specials += SDRTristate(pad, _out, _oe, _in)
                    start += len(pad)
            else:
                self.specials += SDRTristate(pads, self._out.storage, self._oe.storage, self._in.status)

        # External Tristate.
        else:
            # Tristate inout IOs (For external tristate IO chips or simulation).
            for i in range(nbits):
                self.comb += pads.oe[i].eq(self._oe.storage[i])
                self.comb += pads.o[i].eq(self._out.storage[i])
                self.specials += MultiReg(pads.i[i], self._in.status[i])

        if with_irq:
            self.add_irq(self._in.status)
