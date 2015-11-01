from functools import reduce
from operator import add, or_

from migen import *
from migen.genlib.cdc import PulseSynchronizer

from misoc.interconnect.csr import *
from misoc.cores.dvi_sampler.common import control_tokens


class WER(Module, AutoCSR):
    def __init__(self, period_bits=24):
        self.data = Signal(10)
        self._update = CSR()
        self._value = CSRStatus(period_bits)

        ###

        # pipeline stage 1
        # we ignore the 10th (inversion) bit, as it is independent of the transition minimization
        data_r = Signal(9)
        self.sync.pix += data_r.eq(self.data[:9])

        # pipeline stage 2
        transitions = Signal(8)
        self.comb += [transitions[i].eq(data_r[i] ^ data_r[i+1]) for i in range(8)]
        transition_count = Signal(max=9)
        self.sync.pix += transition_count.eq(reduce(add, [transitions[i] for i in range(8)]))

        is_control = Signal()
        self.sync.pix += is_control.eq(reduce(or_, [data_r == ct for ct in control_tokens]))

        # pipeline stage 3
        is_error = Signal()
        self.sync.pix += is_error.eq((transition_count > 4) & ~is_control)

        # counter
        period_counter = Signal(period_bits)
        period_done = Signal()
        self.sync.pix += Cat(period_counter, period_done).eq(period_counter + 1)

        wer_counter = Signal(period_bits)
        wer_counter_r = Signal(period_bits)
        wer_counter_r_updated = Signal()
        self.sync.pix += [
            wer_counter_r_updated.eq(period_done),
            If(period_done,
                wer_counter_r.eq(wer_counter),
                wer_counter.eq(0)
            ).Elif(is_error,
                wer_counter.eq(wer_counter + 1)
            )
        ]

        # sync to system clock domain
        wer_counter_sys = Signal(period_bits)
        self.submodules.ps_counter = PulseSynchronizer("pix", "sys")
        self.comb += self.ps_counter.i.eq(wer_counter_r_updated)
        self.sync += If(self.ps_counter.o, wer_counter_sys.eq(wer_counter_r))

        # register interface
        self.sync += If(self._update.re, self._value.status.eq(wer_counter_sys))
