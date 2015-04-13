from migen.fhdl.std import *
from migen.bus import wishbone
from migen.bank.bank import GenericBank

class Bank(GenericBank):
    def __init__(self, description, bus=None):
        if bus is None:
            bus = wishbone.Interface()
        self.bus = bus

        ###

        GenericBank.__init__(self, description, flen(self.bus.dat_w))

        for i, c in enumerate(self.simple_csrs):
            self.comb += [
                c.r.eq(self.bus.dat_w[:c.size]),
                c.re.eq(self.bus.cyc & self.bus.stb & ~self.bus.ack & self.bus.we & \
                    (self.bus.adr[:self.decode_bits] == i))
            ]

        brcases = dict((i, self.bus.dat_r.eq(c.w)) for i, c in enumerate(self.simple_csrs))
        self.sync += [
            Case(self.bus.adr[:self.decode_bits], brcases),
            If(bus.ack, bus.ack.eq(0)).Elif(bus.cyc & bus.stb, bus.ack.eq(1))
        ]
