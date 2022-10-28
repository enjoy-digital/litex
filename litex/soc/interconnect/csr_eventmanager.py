#
# This file is part of LiteX.
#
# Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2016-2019 Tim 'mithro' Ansell <me@mith.ro>
# SPDX-License-Identifier: BSD-2-Clause

"""
The event manager provides a systematic way to generate standard interrupt
controllers.
"""

from migen import *
from migen.util.misc import xdir
from migen.fhdl.tracer import get_obj_var_name

from litex.gen import *

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
    """EventSource which triggers on a Falling or Rising edge.

    The purpose of this event source is to monitor the status of processes and
    generate an interrupt on their completion.
    """
    def __init__(self, name=None, description=None, edge="falling"):
        assert edge in ["falling", "rising"]
        _EventSource.__init__(self, name, description)
        self.comb += self.status.eq(self.trigger)
        trigger_d = Signal()
        self.sync += If(self.clear, self.pending.eq(0))
        self.sync += trigger_d.eq(self.trigger)
        if edge == "falling":
            self.sync += If(~self.trigger & trigger_d, self.pending.eq(1))
        if edge == "rising":
            self.sync += If(self.trigger & ~trigger_d, self.pending.eq(1))


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
        sources   = sorted(sources_u, key=lambda x: x.duid)
        n         = len(sources)

        # Common
        def get_source_name(src, i):
            r = getattr(src, "name", None)
            if r is None:
                r = f"event{i}"
            return r

        def get_pending_source_description(src):
            r = ""
            if getattr(src, "name", None) is not None:
                r += "`1` if a `{}` event occurred. ".format(src.name)
            else:
                r += "`1` if a this particular event occurred. "
            if getattr(src, "description", None) is not None:
                return src.description
            elif isinstance(src, EventSourceLevel):
                return r + "This Event is **level triggered** when the signal is **high**."
            elif isinstance(src, EventSourcePulse):
                return r + "This Event is triggered on a **rising** edge."
            elif isinstance(src, EventSourceProcess):
                return r + "This Event is triggered on a **falling** edge."
            else:
                return r + "This Event uses an unknown method of triggering."

        # Status register
        fields = []
        for i, source in enumerate(sources):
            # Get source name and use default if None.
            name = get_source_name(source, i)
            # Get description and use default description if None.
            desc = getattr(source, "description", None)
            if desc is None:
                desc = "This register contains the current raw level of the {} event trigger.  Writes to this register have no effect.".format(str(name))
            # Add CSRField
            fields.append(CSRField(name=name, size=1, description=f"Level of the ``{name}`` event"))
        self.status = CSRStatus(n, description=desc, fields=fields)

        # Pending Register
        fields = []
        for i, source in enumerate(sources):
            # Get source name and use default if None.
            name = get_source_name(source, i)
            # Get description and use default description if None.
            desc = getattr(source, "description", None)
            if desc is None:
                desc = "When a  {} event occurs, the corresponding bit will be set in this register.  To clear the Event, set the corresponding bit in this register.".format(str(name))
            # Add CSRField
            fields.append(CSRField(name=name, size=1, description=get_pending_source_description(source)))
        self.pending = CSRStatus(n, description=desc, fields=fields, read_only=False)

        # Enable Register
        fields = []
        for i, source in enumerate(sources):
            # Get source name and use default if None.
            name = get_source_name(source, i)
            # Get description and use default description if None.
            desc = getattr(source, "description", None)
            if desc is None:
                desc = "This register enables the corresponding {} events.  Write a ``0`` to this register to disable individual events.".format(str(name))
            # Add CSRField
            fields.append(CSRField(name=name, offset=i, description=f"Write a ``1`` to enable the ``{name}`` Event"))
        self.enable = CSRStorage(n, description=desc, fields=fields)

        # Connect Events/Fields
        for i, source in enumerate(sources):
            # Get source name and use default if None.
            name = get_source_name(source, i)
            self.comb += [
                getattr(self.status.fields,  name).eq(source.status),
                getattr(self.pending.fields, name).eq(source.pending),
                If(self.pending.re & self.pending.r[i], source.clear.eq(1)),
            ]
            irqs = [self.pending.status[i] & self.enable.storage[i] for i in range(n)]
        self.comb += self.irq.eq(Reduce("OR", irqs))

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
        self.comb += self.irq.eq(Reduce("OR", [ev.irq for ev in event_managers]))
