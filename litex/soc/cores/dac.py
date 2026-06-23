#
# This file is part of LiteX.
#
# Copyright (c) 2022 Tim Callahan <tcal@google.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.soc.interconnect.csr import *

# DAC -----------------------------------------------------------------------------------------------

class DAC(Module, AutoCSR):
    """First-order Sigma-Delta DAC.

    Provides a small one-bit Sigma-Delta DAC output. When
    ``with_constant_transition`` is set, the raw Sigma-Delta bitstream is
    encoded as a 3-cycle symbol:

    - ``1`` -> ``1, 1, 0``
    - ``0`` -> ``1, 0, 0``

    This keeps the output transition activity constant, at the cost of output rate/range.
    """
    def __init__(self, out=None, data_width=12, with_csr=True, with_constant_transition=False):
        if out is None:
            self.out = out = Signal()
        else:
            self.out = out
        self.value = Signal(data_width)

        # # #

        accum      = Signal(data_width + 1, reset_less=True)
        accum_next = Signal(data_width + 1)
        sd_bit     = Signal()

        self.comb += [
            accum_next.eq(accum[:data_width] + self.value),
            sd_bit.eq(accum[data_width]),
        ]

        if with_constant_transition:
            phase = Signal(max=3)
            self.sync += [
                If(phase == 2,
                    phase.eq(0),
                    accum.eq(accum_next)
                ).Else(
                    phase.eq(phase + 1)
                )
            ]
            self.comb += Case(phase, {
                0 : out.eq(1),
                1 : out.eq(sd_bit),
                2 : out.eq(0),
            })
        else:
            self.sync += accum.eq(accum_next)
            self.comb += out.eq(sd_bit)

        if with_csr:
            self.add_csr(data_width)

    def add_csr(self, data_width):
        self._value = CSRStorage(data_width, reset_less=True,
            description="Digital value to convert to analog.")
        self.comb += self.value.eq(self._value.storage)
