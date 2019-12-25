from migen import *

from litex.soc.interconnect.csr import *


class PWM(Module, AutoCSR):
    def __init__(self, pwm):
        self._enable = CSRStorage()
        self._width = CSRStorage(32)
        self._period = CSRStorage(32)

        # # #

        cnt = Signal(32)

        enable = self._enable.storage
        width = self._width.storage
        period = self._period.storage

        self.sync += \
            If(enable,
                If(cnt < width,
                    pwm.eq(1)
                ).Else(
                    pwm.eq(0)
                ),
                If(cnt == period-1,
                    cnt.eq(0)
                ).Else(
                    cnt.eq(cnt+1)
                )
            ).Else(
                cnt.eq(0),
                pwm.eq(0)
            )
