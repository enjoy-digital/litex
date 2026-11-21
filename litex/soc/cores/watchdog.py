#
# This file is part of LiteX.
#
# Copyright (c) 2024 Fin Maaß <f.maass@vogl-electronic.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *
from litex.gen.genlib.misc import WaitTimer

from litex.soc.interconnect.csr import *
from litex.soc.interconnect.csr_eventmanager import *

# Watchdog --------------------------------------------------------------------------------------------

class Watchdog(LiteXModule):
    """Watchdog

    Provides a generic Watchdog core.

    If ``initial_cycles`` is non-zero, the watchdog comes out of reset enabled, in reset mode,
    with a timeout of ``initial_cycles`` cycles. The software must then feed or disable it in time.
    """

    def __init__(self, width=32, crg_rst=None, reset_delay=0, halted=None, initial_cycles=0):
        assert 0 <= initial_cycles < 2**width, f"initial_cycles must fit in {width} bits."

        self.enable = Signal()
        self.reset_mode = Signal()
        self.feed = Signal()
        self.halted = Signal()

        self.execute = Signal()

        enabled_on_startup = bool(initial_cycles)

        self._control = CSRStorage(description="Watchdog Control.", fields=[
            CSRField("feed",   size=1, offset=0, pulse=True,
                     description="Watchdog feed (Write ``1`` to feed)."),
            CSRField("enable", size=1, offset=8,
                     reset=enabled_on_startup, description="Watchdog enable."),
            CSRField("reset",  size=1, offset=16, reset=enabled_on_startup,
                     description="Reset SoC when watchdog times out."),
            CSRField("pause_halted", size=1, offset=24, reset=enabled_on_startup,
                     description="Pause watchdog when CPU is halted.")
        ])

        self.comb += [
            self.enable.eq(self._control.fields.enable & ~self.halted),
            self.feed.eq(self._control.fields.feed),
            self.reset_mode.eq(self._control.fields.reset),
        ]

        if isinstance(halted, Signal):
            self.comb += self.halted.eq(halted & self._control.fields.pause_halted)

        self._cycles = cycles = CSRStorage(
            description="Watchdog cycles until timeout.", size=width, reset=initial_cycles)
        self._remaining = remaining = CSRStatus(
            description="Watchdog cycles remaining until timeout.", size=width, reset=initial_cycles)

        self.ev      = EventManager()
        self.ev.wdt  = EventSourceProcess(edge="rising")
        self.ev.finalize()

        self.sync += [
            If(self.feed, 
                remaining.status.eq(cycles.storage)
            ).Elif(self.enable,
                If(remaining.status != 0,
                    remaining.status.eq(remaining.status - 1)
                ),
                self.execute.eq(remaining.status == 0),
            )
        ]

        self.comb += If(self.enable, self.ev.wdt.trigger.eq(self.execute))

        if isinstance(crg_rst, Signal):
            self.reset_timer = WaitTimer(reset_delay)
            self.comb += self.reset_timer.wait.eq(self.enable & self.execute & self.reset_mode)
            self.comb += If(self.reset_timer.done, crg_rst.eq(1))
