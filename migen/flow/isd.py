from migen.fhdl.std import *
from migen.bank.description import *
from migen.flow.hooks import DFGHook

ISD_MAGIC = 0x6ab4

class EndpointReporter(Module, AutoCSR):
    def __init__(self, endpoint, nbits):
        self.reset = Signal()
        self.freeze = Signal()

        self._ack_count = CSRStatus(nbits)
        self._nack_count = CSRStatus(nbits)
        self._cur_status = CSRStatus(2)

        ###

        stb = Signal()
        ack = Signal()
        self.comb += self._cur_status.status.eq(Cat(stb, ack))
        ack_count = Signal(nbits)
        nack_count = Signal(nbits)
        self.sync += [
            # register monitored signals
            stb.eq(endpoint.stb),
            ack.eq(endpoint.ack),
            # count operations
            If(self.reset,
                ack_count.eq(0),
                nack_count.eq(0)
            ).Else(
                If(stb,
                    If(ack,
                        ack_count.eq(ack_count + 1)
                    ).Else(
                        nack_count.eq(nack_count + 1)
                    )
                )
            ),
            If(~self.freeze,
                self._ack_count.status.eq(ack_count),
                self._nack_count.status.eq(nack_count)
            )
        ]

class DFGReporter(DFGHook, AutoCSR):
    def __init__(self, dfg, nbits):
        self._magic = CSRStatus(16)
        self._neps = CSRStatus(8)
        self._nbits = CSRStatus(8)
        self._freeze = CSRStorage()
        self._reset = CSR()

        ###

        DFGHook.__init__(self, dfg,
            lambda u, ep, v: EndpointReporter(getattr(u, ep), nbits))
        hooks = list(self.hooks_iter())

        self.comb += [
            self._magic.status.eq(ISD_MAGIC),
            self._neps.status.eq(len(hooks)),
            self._nbits.status.eq(nbits)
        ]
        for h in hooks:
            self.comb += [
                h.freeze.eq(self._freeze.storage),
                h.reset.eq(self._reset.re)
            ]
