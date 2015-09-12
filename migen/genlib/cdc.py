from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.fhdl.specials import Special
from migen.fhdl.bitcontainer import value_bits_sign


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


class BusSynchronizer(Module):
    """Clock domain transfer of several bits at once.

    Ensures that all the bits form a single word that was present
    synchronously in the input clock domain (unlike direct use of
    ``MultiReg``)."""
    def __init__(self, width, idomain, odomain):
        self.i = Signal(width)
        self.o = Signal(width)

        if width == 1:
            self.specials += MultiReg(self.i, self.o, odomain)
        else:
            sync_i = getattr(self.sync, idomain)
            sync_o = getattr(self.sync, odomain)

            starter = Signal(reset=1)
            sync_i += starter.eq(0)
            self.submodules._ping = PulseSynchronizer(idomain, odomain)
            self.submodules._pong = PulseSynchronizer(odomain, idomain)
            self.comb += [
                self._ping.i.eq(starter | self._pong.o),
                self._pong.i.eq(self._ping.i)
            ]

            ibuffer = Signal(width)
            obuffer = Signal(width)
            sync_i += If(self._pong.o, ibuffer.eq(self.i))
            self.specials += MultiReg(ibuffer, obuffer, odomain)
            sync_o += If(self._ping.o, self.o.eq(obuffer))


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
