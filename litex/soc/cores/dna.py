# This file is Copyright (c) 2014-2015 Robert Jordens <jordens@gmail.com>
# License: BSD

from migen import *

from litex.soc.interconnect.csr import *


class DNA(Module, AutoCSR):
    def __init__(self):
        n = 57
        self._id = CSRStatus(n)

        # # #

        do = Signal()
        cnt = Signal(max=2*n + 1)

        self.specials += Instance("DNA_PORT",
                i_DIN=self._id.status[-1], o_DOUT=do,
                i_CLK=cnt[0], i_READ=cnt < 2, i_SHIFT=1)

        self.sync += \
                If(cnt < 2*n,
                    cnt.eq(cnt + 1),
                    If(cnt[0],
                        self._id.status.eq(Cat(do, self._id.status))
                    )
                )
