from migen.actorlib.packet import Arbiter, Dispatcher, Status
from migen.flow.plumbing import Multiplexer

from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.frontend.common import *
from misoclib.mem.litesata.frontend.striping import LiteSATAStripingTX, LiteSATAStripingRX


class LiteSATAMirroringCtrl(Module):
    def __init__(self, n):
        self.new_cmds = Signal(n)
        self.ack_cmds = Signal(n)

        self.reading = Signal()
        self.writing = Signal()

        self.wants_write = Signal()
        self.write_sel = Signal(max=n)

        # # #

        pending_cmds = Signal(n)
        self.sync += pending_cmds.eq(self.new_cmds | (pending_cmds & ~self.ack_cmds))
        can_commute = Signal()
        self.comb += can_commute.eq((pending_cmds | self.new_cmds)  == 0)

        self.fsm = fsm = FSM(reset_state="READ")
        self.submodules += fsm
        fsm.act("READ",
            self.reading.eq(1),
            If(self.wants_write & can_commute,
                NextState("WRITE")
            )
        )
        fsm.act("WRITE",
            self.writing.eq(1),
            If(~self.wants_write & can_commute,
                NextState("READ")
            )
        )


class LiteSATAMirroringTX(Module):
    def __init__(self, n, dw, ctrl):
        self.sinks = sinks = [Sink(command_tx_description(dw)) for i in range(n)]
        self.sources = sources = [Source(command_tx_description(dw)) for i in range(n)]

        # # #

        wants_write = Signal()

        reading = Signal()
        writing = Signal()

        reads = [Sink(command_tx_description(dw)) for i in range(dw)]
        writes = [Sink(command_tx_description(dw)) for i in range(dw)]
        for sink, read, write in zip(sinks, reads, writes):
            read_stall = Signal()
            read_status = Status(read)
            self.submodules += read_status
            self.comb += [
                Record.connect(sink, read, leave_out=set(["stb", "ack"])),
                Record.connect(sink, write, leave_out=set(["stb", "ack"])),
                read.stb.eq(sink.stb & (sink.read | sink.identify) & ~read_stall),
                write.stb.eq(sink.stb & sink.write),
                If(sink.read | sink.identify,
                    sink.ack.eq((read.ack & ~read_stall))
                ).Else(
                    sink.ack.eq(write.ack)
                )
            ]
            self.sync += \
                If(~ctrl.wants_write,
                    read_stall.eq(0)
                ).Elif(~read_status.ongoing,
                    read_stall.eq(1)
                )

        write_striper = LiteSATAStripingTX(n, dw, mirroring_mode=True)
        write_arbiter = Arbiter(writes, write_striper.sink)
        self.submodules += write_striper, write_arbiter

        for i in range(n):
            source_status = Status(sources[i])
            self.submodules += source_status
            self.comb += [
                If(ctrl.reading,
                    Record.connect(reads[i], sources[i]) # independent reads
                ).Elif(ctrl.writing,
                    Record.connect(write_striper.sources[i], sources[i]) # identical writes
                ),
                ctrl.new_cmds[i].eq(source_status.eop)
            ]
        write_striper_sink_status = Status(write_striper.sink)
        self.submodules += write_striper_sink_status
        self.comb += [
            ctrl.wants_write.eq(write_striper_sink_status.ongoing),
            ctrl.write_sel.eq(write_arbiter.rr.grant)
        ]


class LiteSATAMirroringRX(Module):
    def __init__(self, n, dw, ctrl):
        self.sinks = sinks = [Sink(command_rx_description(dw)) for i in range(n)]
        self.sources = sources = [Source(command_rx_description(dw)) for i in range(n)]

        # # #

        muxs = [Multiplexer(command_rx_description(dw), 2) for i in range(n)]
        self.submodules += muxs

        writes = [mux.sink0 for mux in muxs]
        reads = [mux.sink1 for mux in muxs]

        for mux, source in zip(muxs, sources):
            self.comb += [
                mux.sel.eq(ctrl.reading),
                Record.connect(mux.source, source)
            ]

        write_striper = LiteSATAStripingRX(n, dw, mirroring_mode=True)
        write_dispatcher = Dispatcher(write_striper.source, writes)
        self.comb += write_dispatcher.sel.eq(ctrl.write_sel)
        self.submodules += write_striper, write_dispatcher

        for i in range(n):
            sink_status = Status(sinks[i])
            self.submodules += sink_status
            self.comb += [
                Record.connect(sinks[i], reads[i], leave_out=set(["stb", "ack"])),
                Record.connect(sinks[i], write_striper.sinks[i], leave_out=set(["stb", "ack"])),
                reads[i].stb.eq(sinks[i].stb & ctrl.reading),
                write_striper.sinks[i].stb.eq(sinks[i].stb & ctrl.writing),
                sinks[i].ack.eq(reads[i].ack | write_striper.sinks[i].ack),
                ctrl.ack_cmds[i].eq(sink_status.eop & sinks[i].last)
            ]


class LiteSATAMirroring(Module):
    """SATA Mirroring

    The mirroring module handles N controllers and provides N ports.
    Each port has its dedicated controller for reads:
        port0 <----> controller0
        portX <----> controllerX
        portN <----> controllerN

    Writes are mirrored on each controller:
                   (port0 write)           |            (portN write)
        port0 ----------+----> controller0 | port0 (stalled) +-----> controller0
        portX (stalled) +----> controllerX | portX (stalled) +-----> controllerX
        portN (stalled) +----> controllerN | portN ----------+-----> controllerN

    Writes have priority on reads. When a write is presented on one of the port, the
    module waits for all ongoing reads to finish and commute to write mode. Once all writes are
    serviced it returns to read mode.

    Characteristics:
        - port's visible capacity = controller's visible capacity
        - total writes throughput = (slowest) controller's throughput
        - total reads throughput = N x controller's throughput

    Can be used for data redundancy and/or to increase total reads speed.
    """
    def __init__(self, controllers):
        n = len(controllers)
        dw = flen(controllers[0].sink.data)
        self.ports = [LiteSATAUserPort(dw) for i in range(n)]

        # # #

        self.submodules.ctrl = LiteSATAMirroringCtrl(n)
        self.submodules.tx = LiteSATAMirroringTX(n, dw, self.ctrl)
        self.submodules.rx = LiteSATAMirroringRX(n, dw, self.ctrl)
        for i in range(n):
            self.comb += [
                Record.connect(self.ports[i].sink, self.tx.sinks[i]),
                Record.connect(self.tx.sources[i], controllers[i].sink),

                Record.connect(controllers[i].source, self.rx.sinks[i]),
                Record.connect(self.rx.sources[i], self.ports[i].source)
            ]
