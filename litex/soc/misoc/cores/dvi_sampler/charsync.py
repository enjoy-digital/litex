from functools import reduce
from operator import or_

from migen import *
from migen.genlib.cdc import MultiReg

from misoc.interconnect.csr import *
from misoc.cores.dvi_sampler.common import control_tokens


class CharSync(Module, AutoCSR):
    def __init__(self, required_controls=8):
        self.raw_data = Signal(10)
        self.synced = Signal()
        self.data = Signal(10)

        self._char_synced = CSRStatus()
        self._ctl_pos = CSRStatus(bits_for(9))

        ###

        raw_data1 = Signal(10)
        self.sync.pix += raw_data1.eq(self.raw_data)
        raw = Signal(20)
        self.comb += raw.eq(Cat(raw_data1, self.raw_data))

        found_control = Signal()
        control_position = Signal(max=10)
        self.sync.pix += found_control.eq(0)
        for i in range(10):
            self.sync.pix += If(reduce(or_, [raw[i:i+10] == t for t in control_tokens]),
                  found_control.eq(1),
                  control_position.eq(i)
            )

        control_counter = Signal(max=required_controls)
        previous_control_position = Signal(max=10)
        word_sel = Signal(max=10)
        self.sync.pix += [
            If(found_control & (control_position == previous_control_position),
                If(control_counter == (required_controls - 1),
                    control_counter.eq(0),
                    self.synced.eq(1),
                    word_sel.eq(control_position)
                ).Else(
                    control_counter.eq(control_counter + 1)
                )
            ).Else(
                control_counter.eq(0)
            ),
            previous_control_position.eq(control_position)
        ]
        self.specials += MultiReg(self.synced, self._char_synced.status)
        self.specials += MultiReg(word_sel, self._ctl_pos.status)

        self.sync.pix += self.data.eq(raw >> word_sel)
