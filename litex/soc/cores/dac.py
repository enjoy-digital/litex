#
# This file is part of LiteX.
#
# Copyright (c) 2022 Tim Callahan <tcal@google.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.soc.interconnect.csr import *

# DAC  ---------------------------------------------------------------------------------------

class DAC(Module, AutoCSR):

    def __init__(self, out, data_width):
        self.out    = out

        self._value = CSRStorage(data_width, reset_less=True, description="Digital value to convert to analog.")
        value       = Signal(data_width)
        accum       = Signal(data_width+1)

        self.comb   += value.eq(self._value.storage)
        self.sync   += accum.eq(accum[0:data_width] + value)
        self.comb   += out.eq(accum[data_width])
