"""
Clock domain crossing module
"""
from math import gcd

from migen import *

from migen.genlib.cdc import MultiReg, PulseSynchronizer
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen.genlib.misc import WaitTimer


class BusSynchronizer(Module):
    """Clock domain transfer of several bits at once.

    Ensures that all the bits form a single word that was present
    synchronously in the input clock domain (unlike direct use of
    ``MultiReg``)."""
    def __init__(self, width, idomain, odomain, timeout=128):
        self.i = Signal(width)
        self.o = Signal(width, reset_less=True)

        if width == 1:
            self.specials += MultiReg(self.i, self.o, odomain)
        else:
            sync_i = getattr(self.sync, idomain)
            sync_o = getattr(self.sync, odomain)

            starter = Signal(reset=1)
            sync_i += starter.eq(0)
            self.submodules._ping = PulseSynchronizer(idomain, odomain)
            # Extra flop on i->o to avoid race between data and request
            # https://github.com/m-labs/nmigen/pull/40#issuecomment-484166790
            ping_o = Signal()
            sync_o += ping_o.eq(self._ping.o)
            self.submodules._pong = PulseSynchronizer(odomain, idomain)
            self.submodules._timeout = ClockDomainsRenamer(idomain)(
                WaitTimer(timeout))
            self.comb += [
                self._timeout.wait.eq(~self._ping.i),
                self._ping.i.eq(starter | self._pong.o | self._timeout.done),
                self._pong.i.eq(ping_o)
            ]

            ibuffer = Signal(width, reset_less=True)
            obuffer = Signal(width)  # registered reset_less by MultiReg
            sync_i += If(self._pong.o, ibuffer.eq(self.i))
            ibuffer.attr.add("no_retiming")
            self.specials += MultiReg(ibuffer, obuffer, odomain)
            sync_o += If(ping_o, self.o.eq(obuffer))


class ElasticBuffer(Module):
    def __init__(self, width, depth, idomain, odomain):
        self.din = Signal(width)
        self.dout = Signal(width)

        # # #

        reset = Signal()
        cd_write = ClockDomain()
        cd_read = ClockDomain()
        self.comb += [
            cd_write.clk.eq(ClockSignal(idomain)),
            cd_read.clk.eq(ClockSignal(odomain)),
            reset.eq(ResetSignal(idomain) | ResetSignal(odomain))
        ]
        self.specials += [
            AsyncResetSynchronizer(cd_write, reset),
            AsyncResetSynchronizer(cd_read, reset)
        ]
        self.clock_domains += cd_write, cd_read

        wrpointer = Signal(max=depth, reset=depth//2)
        rdpointer = Signal(max=depth)

        storage = Memory(width, depth)
        self.specials += storage

        wrport = storage.get_port(write_capable=True, clock_domain="write")
        rdport = storage.get_port(clock_domain="read")
        self.specials += wrport, rdport

        self.sync.write += wrpointer.eq(wrpointer + 1)
        self.sync.read += rdpointer.eq(rdpointer + 1)

        self.comb += [
            wrport.we.eq(1),
            wrport.adr.eq(wrpointer),
            wrport.dat_w.eq(self.din),

            rdport.adr.eq(rdpointer),
            self.dout.eq(rdport.dat_r)
        ]
