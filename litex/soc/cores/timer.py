# This file is Copyright (c) 2013-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# License: BSD


from migen import *

from litex.soc.interconnect.csr import *
from litex.soc.interconnect.csr_eventmanager import *


class Timer(Module, AutoCSR):
    def __init__(self, width=32):
        self._load = CSRStorage(width, description="""This is the initial value loaded into the
                                        timer.  You can make a one-shot timer by disabling the
                                        timer, writing to this register, and then re-enabling
                                        the timer.  For a recurring timer, set this to the same
                                        value as `reload`, or to 0.""")
        self._reload = CSRStorage(width, description="""The internal timer value will be updated
                                        with this value whenever it reaches 0.  Use this to create
                                        a periodic timer that fires whenever this transitions from
                                        0 to >0.  To create a one-shot timer, leave this value as 0.""")
        self._en = CSRStorage(fields=[CSRField("en", description="Write a `1` here to start the timer running")])
        self._update_value = CSRStorage(fields=[CSRField("update", description="""Writing to this register causes
                                        the `value` register to be updated with with the current countdown
                                        value.""")])
        self._value = CSRStatus(width, description="""Last snapshotted value of the countdown
                                        timer.  This value is only updated when a `1` is written
                                        to `update_value`.""")

        self.submodules.ev = EventManager()
        self.ev.zero = EventSourceProcess()
        self.ev.finalize()

        ###

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
