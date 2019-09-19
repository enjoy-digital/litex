# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2016-2019 Tim 'mithro' Ansell <me@mith.ro>
# License: BSD

"""
The event manager provides a systematic way to generate standard interrupt
controllers.
"""

from functools import reduce
from operator import or_

from migen import *
from migen.util.misc import xdir
from migen.fhdl.tracer import get_obj_var_name

from litex.soc.interconnect.csr import *


class _EventSource(DUID):
    """Base class for EventSources.

    Attributes
    ----------
    trigger : Signal(), in
        Signal which interfaces with the user design.

    status : Signal(), out
        Contains the current level of the trigger signal.
        This value ends up in the ``status`` register.

    pending : Signal(), out
        A trigger event has occurred and not yet cleared.
        This value ends up in the ``pending`` register.

    clear : Signal(), in
        Clear after a trigger event.
        Ignored by some event sources.

    name : str
        A short name for this EventSource, usable as a Python identifier

    description: str
        A formatted description of this EventSource, including when
        it will fire and how it behaves.
    """

    def __init__(self, name=None, description=None):
        DUID.__init__(self)
        self.status = Signal()
        self.pending = Signal()
        self.trigger = Signal()
        self.clear = Signal()
        self.name = get_obj_var_name(name)
        self.description = description


class EventSourcePulse(Module, _EventSource):
    """EventSource which triggers on a pulse.

    The event stays asserted after the ``trigger`` signal goes low, and until
    software acknowledges it.

    An example use is to pulse ``trigger`` high for 1 cycle after the reception
    of a character in a UART.
    """

    def __init__(self, name=None, description=None):
        _EventSource.__init__(self, name, description)
        self.comb += self.status.eq(0)
        self.sync += [
            If(self.clear, self.pending.eq(0)),
            If(self.trigger, self.pending.eq(1))
        ]


class EventSourceProcess(Module, _EventSource):
    """EventSource which triggers on a falling edge.

    The purpose of this event source is to monitor the status of processes and
    generate an interrupt on their completion.
    """
    def __init__(self, name=None, description=None):
        _EventSource.__init__(self, name, description)
        self.comb += self.status.eq(self.trigger)
        old_trigger = Signal()
        self.sync += [
            If(self.clear, self.pending.eq(0)),
            old_trigger.eq(self.trigger),
            If(~self.trigger & old_trigger, self.pending.eq(1))
        ]


class EventSourceLevel(Module, _EventSource):
    """EventSource which trigger contains the instantaneous state of the event.

    It must be set and released by the user design. For example, a DMA
    controller with several slots can use this event source to signal that one
    or more slots require CPU attention.
    """
    def __init__(self, name=None, description=None):
        _EventSource.__init__(self, name, description)
        self.comb += [
            self.status.eq(self.trigger),
            self.pending.eq(self.trigger)
        ]


class EventManager(Module, AutoCSR):
    """Provide an IRQ and CSR registers for a set of event sources.

    Each event source is assigned one bit in each of those registers.

    Attributes
    ----------
    irq : Signal(), out
        A signal which is driven high whenever there is a pending and unmasked
        event.
        It is typically connected to an interrupt line of a CPU.

    status : CSR(n), read-only
        Contains the current level of the trigger line of
        ``EventSourceProcess`` and ``EventSourceLevel`` sources.
        It is always 0 for ``EventSourcePulse``

    pending : CSR(n), read-write
        Contains the currently asserted events. Writing 1 to the bit assigned
        to an event clears it.

    enable : CSR(n), read-write
        Defines which asserted events will cause the ``irq`` line to be
        asserted.
    """

    def __init__(self):
        self.irq = Signal()

    def do_finalize(self):
        sources_u = [v for k, v in xdir(self, True) if isinstance(v, _EventSource)]
        sources = sorted(sources_u, key=lambda x: x.duid)
        n = len(sources)
        self.status = CSR(n)
        self.pending = CSR(n)
        self.enable = CSRStorage(n)

        for i, source in enumerate(sources):
            self.comb += [
                self.status.w[i].eq(source.status),
                If(self.pending.re & self.pending.r[i], source.clear.eq(1)),
                self.pending.w[i].eq(source.pending)
            ]

        irqs = [self.pending.w[i] & self.enable.storage[i] for i in range(n)]
        self.comb += self.irq.eq(reduce(or_, irqs))

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        if isinstance(value, _EventSource):
            if self.finalized:
                raise FinalizeError
            self.submodules += value


class SharedIRQ(Module):
    """Allow an IRQ signal to be shared between multiple EventManager objects."""

    def __init__(self, *event_managers):
        self.irq = Signal()
        self.comb += self.irq.eq(reduce(or_, [ev.irq for ev in event_managers]))
