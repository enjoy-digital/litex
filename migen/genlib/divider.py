from migen.fhdl.structure import *
from migen.fhdl.module import Module


class Divider(Module):
    def __init__(self, w):
        self.start_i = Signal()
        self.dividend_i = Signal(w)
        self.divisor_i = Signal(w)
        self.ready_o = Signal()
        self.quotient_o = Signal(w)
        self.remainder_o = Signal(w)

        ###

        qr = Signal(2*w)
        counter = Signal(max=w+1)
        divisor_r = Signal(w)
        diff = Signal(w+1)

        self.comb += [
            self.quotient_o.eq(qr[:w]),
            self.remainder_o.eq(qr[w:]),
            self.ready_o.eq(counter == 0),
            diff.eq(qr[w-1:] - divisor_r)
        ]
        self.sync += [
            If(self.start_i,
                counter.eq(w),
                qr.eq(self.dividend_i),
                divisor_r.eq(self.divisor_i)
            ).Elif(~self.ready_o,
                    If(diff[w],
                        qr.eq(Cat(0, qr[:2*w-1]))
                    ).Else(
                        qr.eq(Cat(1, qr[:w-1], diff[:w]))
                    ),
                    counter.eq(counter - 1)
            )
        ]
