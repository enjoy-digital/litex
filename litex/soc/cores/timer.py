# This file is Copyright (c) 2013-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2019 Sean Cross <sean@xobs.io>
# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD


from migen import *

from litex.soc.interconnect.csr import *
from litex.soc.interconnect.csr_eventmanager import *
from litex.soc.integration.doc import ModuleDoc

class Timer(Module, AutoCSR, ModuleDoc):
    """Timer

    Provides a generic Timer core.

    The Timer is implemented as a countdown timer that can be used in various modes:
    - Polling : Returns current countdown value to software.
    - One-Shot: Loads itself and stops when value reaches 0.
    - Periodic: (Re-)Loads itself when value reaches 0.

    `en` register allows the user to enable/disable the Timer. When the Timer is enabled, it is
    automatically loaded with the value of `load` register.

    When the Timer reaches 0, it is automatically reloaded with value of `reload` register.

    The user can latch the current countdown value by writing to `update_value` register, it will
    update `value` register with current countdown value.

    To use the Timer in One-Shot mode, the user needs to:
    - Disable the timer.
    - Set the `load` register to the expected duration.
    - (Re-)Enable the Timer.

    To use the Timer in Periodic mode, the user needs to:
    - Disable the Timer.
    - Set the `load` register to 0.
    - Set the `reload` register to the expected period.
    - Enable the Timer.

    For both modes, the CPU can be advertised by an IRQ that the duration/period has elapsed. (The
    CPU can also do software polling with `update_value` and `value` to know the elapsed duration)
    """
    def __init__(self, width=32):
        self._load = CSRStorage(width, description="""Load value when Timer is (re-)enabled.""" +
            """In One-Shot mode, the value written to this register specify the Timer's duration in
            clock cycles.""")
        self._reload = CSRStorage(width, description="""Reload value when Timer reaches 0.""" +
            """In Periodic mode, the value written to this register specify the Timer's period in
            clock cycles.""")
        self._en = CSRStorage(1, description="""Enable of the Timer.""" +
            """Set if to 1 to enable/start the Timer and 0 to disable the Timer""")
        self._update_value = CSRStorage(1, description="""Update of the current countdown value."""+
            """A write to this register latches the current countdown value to `value` register.""")
        self._value = CSRStatus(width, description="""Latched countdown value""")

        self.submodules.ev = EventManager()
        self.ev.zero = EventSourceProcess()
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
        self.comb += self.ev.zero.trigger.eq(value != 0)
