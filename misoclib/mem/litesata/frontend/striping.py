from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.frontend.common import *


class LiteSATAStripingTX(Module):
    """SATA Striping TX

    Split cmds and writes data on N different controllers.

    This module provides a mirroring_mode that is used by the mirroring module to
    dispatch identicals writes to the controllers. This avoid code duplication in
    between striping and mirroring modules. In this special case, port's data width
    is dw (same as controllers)
    """
    def __init__(self, n, dw, mirroring_mode=False):
        self.sink = sink = Sink(command_tx_description(dw*n if not mirroring_mode else dw))
        self.sources = sources = [Source(command_tx_description(dw)) for i in range(n)]

        # # #

        split = Signal()

        already_acked = Signal(n)
        self.sync += If(split & sink.stb,
                already_acked.eq(already_acked | Cat(*[s.ack for s in sources])),
                If(sink.ack, already_acked.eq(0))
            )

        self.fsm = fsm = FSM(reset_state="IDLE")
        self.submodules += fsm
        fsm.act("IDLE",
            sink.ack.eq(0),
            If(sink.stb & sink.sop,
                NextState("SPLIT")
            ).Else(
                sink.ack.eq(1)
            )
        )

        # split data and ctrl signals (except stb & ack managed in fsm)
        for i, s in enumerate(sources):
            self.comb += Record.connect(sink, s, leave_out=["stb", "ack", "data"])
            if mirroring_mode:
                self.comb += s.data.eq(sink.data)
            else:
                self.comb += s.data.eq(sink.data[i*dw:(i+1)*dw])

        fsm.act("SPLIT",
            split.eq(1),
            [s.stb.eq(sink.stb & ~already_acked[i]) for i, s in enumerate(sources)],
            sink.ack.eq(optree("&", [s.ack | already_acked[i] for i, s in enumerate(sources)])),
            If(sink.stb & sink.eop & sink.ack,
                NextState("IDLE")
            )
        )

class LiteSATAStripingRX(Module):
    """SATA Striping RX

    Combine acknowledges and reads data from N different controllers.

    This module provides a mirroring_mode that is used by the mirroring module to
    dispatch identicals writes to the controllers. This avoid code duplication in
    between striping and mirroring modules. In this special case, port's data width
    is dw (same as controllers)
    """
    def __init__(self, n, dw, mirroring_mode=False):
        self.sinks = sinks = [Sink(command_rx_description(dw)) for i in range(n)]
        self.source = source = Source(command_rx_description(dw*n if not mirroring_mode else dw))

        # # #

        sop = Signal()
        self.comb += sop.eq(optree("&", [s.stb & s.sop for s in sinks]))

        self.fsm = fsm = FSM(reset_state="IDLE")
        self.submodules += fsm
        fsm.act("IDLE",
            If(sop,
                NextState("COMBINE")
            )
        )

        # use first sink for ctrl signals (except for stb, ack & failed)
        self.comb += Record.connect(sinks[0], source, leave_out=["stb", "ack", "failed", "data"])
		# combine datas
        if mirroring_mode:
            self.comb += source.data.eq(0) # mirroring only used for writes
        else:
            for i, s in enumerate(sinks):
                self.comb += source.data[i*dw:(i+1)*dw].eq(s.data)


        fsm.act("COMBINE",
            source.failed.eq(optree("|", [s.failed for s in sinks])), # XXX verify this is enough
            source.stb.eq(optree("&", [s.stb for s in sinks])),
            [s.ack.eq(source.stb & source.ack) for s in sinks],
            If(source.stb & source.eop & source.ack,
                NextState("IDLE")
            )
        )


class LiteSATAStriping(Module):
    """SATA Striping

    Segment data so that data is stored on N different controllers.
                     +----> controller0 (dw)
    port (N*dw) <----+----> controllerX (dw)
                     +----> controllerN (dw)

    Characteristics:
        - master's visible capacity = N x controller's visible capacity
        - master's throughput = N x (slowest) controller's throughput

    Can be used to increase capacity and writes/reads throughput.
    """
    def __init__(self, controllers):

        # # #
        n = len(controllers)
        dw = flen(controllers[0].sink.data)

        self.submodules.tx = LiteSATAStripingTX(n, dw)
        self.submodules.rx = LiteSATAStripingRX(n, dw)
        for i in range(n):
            self.comb += [
                Record.connect(self.tx.sources[i], controllers[i].sink),
                Record.connect(controllers[i].source, self.rx.sinks[i])
            ]
        self.sink, self.source = self.tx.sink, self.rx.source
