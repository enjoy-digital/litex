from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.fhdl.bitcontainer import bits_for


def split(v, *counts):
    r = []
    offset = 0
    for n in counts:
        if n != 0:
            r.append(v[offset:offset+n])
        else:
            r.append(None)
        offset += n
    return tuple(r)


def displacer(signal, shift, output, n=None, reverse=False):
    if shift is None:
        return output.eq(signal)
    if n is None:
        n = 2**len(shift)
    w = len(signal)
    if reverse:
        r = reversed(range(n))
    else:
        r = range(n)
    l = [Replicate(shift == i, w) & signal for i in r]
    return output.eq(Cat(*l))


def chooser(signal, shift, output, n=None, reverse=False):
    if shift is None:
        return output.eq(signal)
    if n is None:
        n = 2**len(shift)
    w = len(output)
    cases = {}
    for i in range(n):
        if reverse:
            s = n - i - 1
        else:
            s = i
        cases[i] = [output.eq(signal[s*w:(s+1)*w])]
    return Case(shift, cases).makedefault()


def timeline(trigger, events):
    lastevent = max([e[0] for e in events])
    counter = Signal(max=lastevent+1)

    counterlogic = If(counter != 0,
        counter.eq(counter + 1)
    ).Elif(trigger,
        counter.eq(1)
    )
    # insert counter reset if it doesn't naturally overflow
    # (test if lastevent+1 is a power of 2)
    if (lastevent & (lastevent + 1)) != 0:
        counterlogic = If(counter == lastevent,
            counter.eq(0)
        ).Else(
            counterlogic
        )

    def get_cond(e):
        if e[0] == 0:
            return trigger & (counter == 0)
        else:
            return counter == e[0]
    sync = [If(get_cond(e), *e[1]) for e in events]
    sync.append(counterlogic)
    return sync


class WaitTimer(Module):
    def __init__(self, t):
        self.wait = Signal()
        self.done = Signal()

        # # #

        count = Signal(bits_for(t), reset=t)
        self.comb += self.done.eq(count == 0)
        self.sync += \
            If(self.wait,
                If(~self.done, count.eq(count - 1))
            ).Else(count.eq(count.reset))


class BitSlip(Module):
    def __init__(self, dw):
        self.i = Signal(dw)
        self.o = Signal(dw)
        self.value = Signal(max=dw)

        # # #

        r = Signal(2*dw)
        self.sync += r.eq(Cat(r[dw:], self.i))
        cases = {}
        for i in range(dw):
            cases[i] = self.o.eq(r[i:dw+i])
        self.sync += Case(self.value, cases)
