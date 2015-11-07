from migen import *
from migen.genlib.misc import timeline
from migen.genlib.fsm import FSM

from misoc.cores.lasmicon.multiplexer import *


class Refresher(Module):
    def __init__(self, a, ba, tRP, tREFI, tRFC):
        self.req = Signal()
        self.ack = Signal()  # 1st command 1 cycle after assertion of ack
        self.cmd = CommandRequest(a, ba)

        ###

        # Refresh sequence generator:
        # PRECHARGE ALL --(tRP)--> AUTO REFRESH --(tRFC)--> done
        seq_start = Signal()
        seq_done = Signal()
        self.sync += [
            self.cmd.a.eq(2**10),
            self.cmd.ba.eq(0),
            self.cmd.cas_n.eq(1),
            self.cmd.ras_n.eq(1),
            self.cmd.we_n.eq(1),
            seq_done.eq(0)
        ]
        self.sync += timeline(seq_start, [
            (1, [
                self.cmd.ras_n.eq(0),
                self.cmd.we_n.eq(0)
            ]),
            (1+tRP, [
                self.cmd.cas_n.eq(0),
                self.cmd.ras_n.eq(0)
            ]),
            (1+tRP+tRFC, [
                seq_done.eq(1)
            ])
        ])

        # Periodic refresh counter
        counter = Signal(max=tREFI)
        start = Signal()
        self.sync += [
            start.eq(0),
            If(counter == 0,
                start.eq(1),
                counter.eq(tREFI - 1)
            ).Else(
                counter.eq(counter - 1)
            )
        ]

        # Control FSM
        fsm = FSM()
        self.submodules += fsm
        fsm.act("IDLE", If(start, NextState("WAIT_GRANT")))
        fsm.act("WAIT_GRANT",
            self.req.eq(1),
            If(self.ack,
                seq_start.eq(1),
                NextState("WAIT_SEQ")
            )
        )
        fsm.act("WAIT_SEQ",
            self.req.eq(1),
            If(seq_done, NextState("IDLE"))
        )
