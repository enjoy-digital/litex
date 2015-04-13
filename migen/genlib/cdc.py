from migen.fhdl.std import *
from migen.fhdl.bitcontainer import value_bits_sign
from migen.fhdl.specials import Special
from migen.fhdl.tools import list_signals


class NoRetiming(Special):
    def __init__(self, reg):
        Special.__init__(self)
        self.reg = reg

    # do nothing
    @staticmethod
    def lower(dr):
        return Module()


class MultiRegImpl(Module):
    def __init__(self, i, o, odomain, n):
        self.i = i
        self.o = o
        self.odomain = odomain

        w, signed = value_bits_sign(self.i)
        self.regs = [Signal((w, signed)) for i in range(n)]

        ###

        src = self.i
        for reg in self.regs:
            sd = getattr(self.sync, self.odomain)
            sd += reg.eq(src)
            src = reg
        self.comb += self.o.eq(src)
        self.specials += [NoRetiming(reg) for reg in self.regs]


class MultiReg(Special):
    def __init__(self, i, o, odomain="sys", n=2):
        Special.__init__(self)
        self.i = i
        self.o = o
        self.odomain = odomain
        self.n = n

    def iter_expressions(self):
        yield self, "i", SPECIAL_INPUT
        yield self, "o", SPECIAL_OUTPUT

    def rename_clock_domain(self, old, new):
        Special.rename_clock_domain(self, old, new)
        if self.odomain == old:
            self.odomain = new

    def list_clock_domains(self):
        r = Special.list_clock_domains(self)
        r.add(self.odomain)
        return r

    @staticmethod
    def lower(dr):
        return MultiRegImpl(dr.i, dr.o, dr.odomain, dr.n)


class PulseSynchronizer(Module):
    def __init__(self, idomain, odomain):
        self.i = Signal()
        self.o = Signal()

        ###

        toggle_i = Signal()
        toggle_o = Signal()
        toggle_o_r = Signal()

        sync_i = getattr(self.sync, idomain)
        sync_o = getattr(self.sync, odomain)

        sync_i += If(self.i, toggle_i.eq(~toggle_i))
        self.specials += MultiReg(toggle_i, toggle_o, odomain)
        sync_o += toggle_o_r.eq(toggle_o)
        self.comb += self.o.eq(toggle_o ^ toggle_o_r)


class GrayCounter(Module):
    def __init__(self, width):
        self.ce = Signal()
        self.q = Signal(width)
        self.q_next = Signal(width)
        self.q_binary = Signal(width)
        self.q_next_binary = Signal(width)

        ###

        self.comb += [
            If(self.ce,
                self.q_next_binary.eq(self.q_binary + 1)
            ).Else(
                self.q_next_binary.eq(self.q_binary)
            ),
            self.q_next.eq(self.q_next_binary ^ self.q_next_binary[1:])
        ]
        self.sync += [
            self.q_binary.eq(self.q_next_binary),
            self.q.eq(self.q_next)
        ]
