#
# This file is part of LiteX.
#
# Copyright (c) 2013-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2019 Sean Cross <sean@xobs.io>
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause


from migen import *

from litex.soc.interconnect.csr import *
from litex.soc.interconnect.csr_eventmanager import *
from litex.soc.integration.doc import AutoDoc, ModuleDoc

# Timer --------------------------------------------------------------------------------------------

class Timer(Module, AutoCSR, AutoDoc):
    with_uptime = False
    def __init__(self, width=32):
        self.intro = ModuleDoc("""Timer

    Provides a generic Timer core.

    The Timer is implemented as a countdown timer that can be used in various modes:

    - Polling : Returns current countdown value to software
    - One-Shot: Loads itself and stops when value reaches ``0``
    - Periodic: (Re-)Loads itself when value reaches ``0``

    ``en`` register allows the user to enable/disable the Timer. When the Timer is enabled, it is
    automatically loaded with the value of `load` register.

    When the Timer reaches ``0``, it is automatically reloaded with value of `reload` register.

    The user can latch the current countdown value by writing to ``update_value`` register, it will
    update ``value`` register with current countdown value.

    To use the Timer in One-Shot mode, the user needs to:

    - Disable the timer
    - Set the ``load`` register to the expected duration
    - (Re-)Enable the Timer

    To use the Timer in Periodic mode, the user needs to:

    - Disable the Timer
    - Set the ``load`` register to 0
    - Set the ``reload`` register to the expected period
    - Enable the Timer

    For both modes, the CPU can be advertised by an IRQ that the duration/period has elapsed. (The
    CPU can also do software polling with ``update_value`` and ``value`` to know the elapsed duration)
    """)
        self._load = CSRStorage(width, description="""Load value when Timer is (re-)enabled.
            In One-Shot mode, the value written to this register specifies the Timer's duration in
            clock cycles.""")
        self._reload = CSRStorage(width, description="""Reload value when Timer reaches ``0``.
            In Periodic mode, the value written to this register specify the Timer's period in
            clock cycles.""")
        self._en = CSRStorage(1, description="""Enable flag of the Timer.
            Set this flag to ``1`` to enable/start the Timer.  Set to ``0`` to disable the Timer.""")
        self._update_value = CSRStorage(1, description="""Update trigger for the current countdown value.
            A write to this register latches the current countdown value to ``value`` register.""")
        self._value = CSRStatus(width, description="""Latched countdown value.
            This value is updated by writing to ``update_value``.""")

        self.submodules.ev = EventManager()
        self.ev.zero       = EventSourceProcess(edge="rising")
        self.ev.finalize()

        # # #

        value = Signal(width)
        self.sync += [
            If(self._en.storage,
                If(value == 0,
                    # set reload to 0 to disable reloading
                    value.eq(self._reload.storage)
                ).Else(
                    value.eq(value - 1)
                )
            ).Else(
                value.eq(self._load.storage)
            ),
            If(self._update_value.re, self._value.status.eq(value))
        ]
        self.comb += self.ev.zero.trigger.eq(value == 0)

    def add_uptime(self, width=64):
        if self.with_uptime: return
        self.with_uptime    = True
        self._uptime_latch  = CSRStorage(description="Write a ``1`` to latch current Uptime cycles to ``uptime_cycles`` register.")
        self._uptime_cycles = CSRStatus(width, description="Latched Uptime since power-up (in ``sys_clk`` cycles).")

        # # #

        self.uptime_cycles = uptime_cycles = Signal(width, reset_less=True)
        self.sync += uptime_cycles.eq(uptime_cycles + 1)
        self.sync += If(self._uptime_latch.re, self._uptime_cycles.status.eq(uptime_cycles))