from migen.fhdl.std import *
from migen.genlib.roundrobin import *
from migen.genlib.record import *
from migen.flow.actor import *
from migen.actorlib.fifo import SyncFIFO
from migen.genlib.fsm import FSM, NextState
from migen.genlib.misc import reverse_bytes


class Status(Module):
    def __init__(self, endpoint):
        self.sop = sop = Signal()
        self.eop = eop =Signal()
        self.ongoing = Signal()

        ongoing = Signal()
        self.comb += \
            If(endpoint.stb,
                sop.eq(endpoint.sop),
                eop.eq(endpoint.eop & endpoint.ack)
            )
        self.sync += ongoing.eq((sop | ongoing) & ~eop)
        self.comb += self.ongoing.eq((sop | ongoing) & ~eop)


class Arbiter(Module):
    def __init__(self, masters, slave):
        if len(masters) == 0:
            pass
        elif len(masters) == 1:
            self.grant = Signal()
            self.comb += Record.connect(masters.pop(), slave)
        else:
            self.submodules.rr = RoundRobin(len(masters))
            self.grant = self.rr.grant
            cases = {}
            for i, master in enumerate(masters):
                status = Status(master)
                self.submodules += status
                self.comb += self.rr.request[i].eq(status.ongoing)
                cases[i] = [Record.connect(master, slave)]
            self.comb += Case(self.grant, cases)


class Dispatcher(Module):
    def __init__(self, master, slaves, one_hot=False):
        if len(slaves) == 0:
            self.sel = Signal()
        elif len(slaves) == 1:
            self.comb += Record.connect(master, slaves.pop())
            self.sel = Signal()
        else:
            if one_hot:
                self.sel = Signal(len(slaves))
            else:
                self.sel = Signal(max=len(slaves))

            # # #

            status = Status(master)
            self.submodules += status

            sel = Signal.like(self.sel)
            sel_ongoing = Signal.like(self.sel)
            self.sync += \
                If(status.sop,
                    sel_ongoing.eq(self.sel)
                )
            self.comb += \
                If(status.sop,
                    sel.eq(self.sel)
                ).Else(
                    sel.eq(sel_ongoing)
                )
            cases = {}
            for i, slave in enumerate(slaves):
                if one_hot:
                    idx = 2**i
                else:
                    idx = i
                cases[idx] = [Record.connect(master, slave)]
            cases["default"] = [master.ack.eq(1)]
            self.comb += Case(sel, cases)


class HeaderField:
    def __init__(self, byte, offset, width):
        self.byte = byte
        self.offset = offset
        self.width = width


class Header:
    def __init__(self, fields, length, swap_field_bytes=True):
        self.fields = fields
        self.length = length
        self.swap_field_bytes = swap_field_bytes

    def get_layout(self):
        layout = []
        for k, v in sorted(self.fields.items()):
            layout.append((k, v.width))
        return layout

    def get_field(self, obj, name, width):
        if "_lsb" in name:
            field = getattr(obj, name.replace("_lsb", ""))[:width]
        elif "_msb" in name:
            field = getattr(obj, name.replace("_msb", ""))[width:2*width]
        else:
            field = getattr(obj, name)
        return field

    def encode(self, obj, signal):
        r = []
        for k, v in sorted(self.fields.items()):
            start = v.byte*8+v.offset
            end = start+v.width
            field = self.get_field(obj, k, v.width)
            if self.swap_field_bytes:
                field = reverse_bytes(field)
            r.append(signal[start:end].eq(field))
        return r

    def decode(self, signal, obj):
        r = []
        for k, v in sorted(self.fields.items()):
            start = v.byte*8+v.offset
            end = start+v.width
            field = self.get_field(obj, k, v.width)
            if self.swap_field_bytes:
                r.append(field.eq(reverse_bytes(signal[start:end])))
            else:
                r.append(field.eq(signal[start:end]))
        return r


class Buffer(Module):
    def __init__(self, description, data_depth, cmd_depth=4, almost_full=None):
        self.sink = sink = Sink(description)
        self.source = source = Source(description)

        # # #

        sink_status = Status(self.sink)
        source_status = Status(self.source)
        self.submodules += sink_status, source_status

        # store incoming packets
        # cmds
        def cmd_description():
            layout = [("error", 1)]
            return EndpointDescription(layout)
        cmd_fifo = SyncFIFO(cmd_description(), cmd_depth)
        self.submodules += cmd_fifo
        self.comb += cmd_fifo.sink.stb.eq(sink_status.eop)
        if hasattr(sink, "error"):
            self.comb += cmd_fifo.sink.error.eq(sink.error)

        # data
        data_fifo = SyncFIFO(description, data_depth, buffered=True)
        self.submodules += data_fifo
        self.comb += [
            Record.connect(self.sink, data_fifo.sink),
            data_fifo.sink.stb.eq(self.sink.stb & cmd_fifo.sink.ack),
            self.sink.ack.eq(data_fifo.sink.ack & cmd_fifo.sink.ack),
        ]

        # output packets
        self.fsm = fsm = FSM(reset_state="IDLE")
        self.submodules += fsm
        fsm.act("IDLE",
            If(cmd_fifo.source.stb,
                NextState("SEEK_SOP")
            )
        )
        fsm.act("SEEK_SOP",
            If(~data_fifo.source.sop,
                data_fifo.source.ack.eq(1)
            ).Else(
                NextState("OUTPUT")
            )
        )
        if hasattr(source, "error"):
            source_error = self.source.error
        else:
            source_error = Signal()

        fsm.act("OUTPUT",
            Record.connect(data_fifo.source, self.source),
            source_error.eq(cmd_fifo.source.error),
            If(source_status.eop,
                cmd_fifo.source.ack.eq(1),
                NextState("IDLE")
            )
        )

        # compute almost full
        if almost_full is not None:
            self.almost_full = Signal()
            self.comb += self.almost_full.eq(data_fifo.fifo.level > almost_full)
