#
# This file is part of LiteX.
#
# Copyright (c) 2017-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import MultiReg, GrayCounter
from migen.genlib.cdc import GrayDecoder

from litex.gen import *

from litex.soc.interconnect.csr import *

# Sampler ------------------------------------------------------------------------------------------

class _Sampler(LiteXModule):
    def __init__(self, width):
        self.latch = Signal()
        self.i     = Signal(width)
        self.o     = Signal(32)

        # # #

        inc   = Signal(width)
        count = Signal(32)

        # Use wrapping property of unsigned arithmeric to reset the counter at each cycle. Doing
        # it in FreqMeter clock domain would not be reliable.
        i_d = Signal(width)
        self.sync += i_d.eq(self.i)
        self.comb += inc.eq(self.i - i_d)
        self.sync += [
            count.eq(count + inc),
            If(self.latch,
                count.eq(0),
                self.o.eq(count)
            )
        ]

# Freq Meter ---------------------------------------------------------------------------------------

class FreqMeter(LiteXModule):
    def __init__(self, period, width=6, clk=None):
        self.clk   = Signal() if clk is None else clk
        self.value = CSRStatus(32)

        # # #

        self.cd_fmeter = ClockDomain(reset_less=True)
        self.comb += self.cd_fmeter.clk.eq(self.clk)

        # Period generation
        period_done    = Signal()
        period_counter = Signal(32)
        self.comb += period_done.eq(period_counter == period)
        self.sync += period_counter.eq(period_counter + 1)
        self.sync += If(period_done, period_counter.eq(0))

        # Frequency measurement
        event_counter = ClockDomainsRenamer("fmeter")(GrayCounter(width))
        gray_decoder  = GrayDecoder(width)
        sampler       = _Sampler(width)
        self.submodules += event_counter, gray_decoder, sampler

        self.specials += MultiReg(event_counter.q, gray_decoder.i)
        self.comb += [
            event_counter.ce.eq(1),
            sampler.latch.eq(period_done),
            sampler.i.eq(gray_decoder.o),
            self.value.status.eq(sampler.o)
        ]
