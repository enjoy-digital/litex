# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *
from migen.genlib.roundrobin import *
from migen.genlib.record import *
from migen.genlib.fsm import FSM, NextState

from litex.gen import *

from litex.soc.interconnect import stream

# Status -------------------------------------------------------------------------------------------

class Status(Module):
    def __init__(self, endpoint):
        self.first   = Signal(reset=1)
        self.last    = Signal()
        self.ongoing = Signal()

        ongoing = Signal()
        self.comb += \
            If(endpoint.valid,
                self.last.eq(endpoint.last & endpoint.ready)
            )
        self.sync += ongoing.eq((endpoint.valid | ongoing) & ~self.last)
        self.comb += self.ongoing.eq((endpoint.valid | ongoing) & ~self.last)

        self.sync += [
            If(self.last,
                self.first.eq(1)
            ).Elif(endpoint.valid & endpoint.ready,
                self.first.eq(0)
            )
        ]

# Arbiter ------------------------------------------------------------------------------------------

class Arbiter(Module):
    def __init__(self, masters, slave):
        if len(masters) == 0:
            pass
        elif len(masters) == 1:
            self.grant = Signal()
            self.comb += masters.pop().connect(slave)
        else:
            self.submodules.rr = RoundRobin(len(masters))
            self.grant = self.rr.grant
            cases = {}
            for i, master in enumerate(masters):
                status = Status(master)
                self.submodules += status
                self.comb += self.rr.request[i].eq(status.ongoing)
                cases[i] = [master.connect(slave)]
            self.comb += Case(self.grant, cases)

# Dispatcher ---------------------------------------------------------------------------------------

class Dispatcher(Module):
    def __init__(self, master, slaves, one_hot=False):
        if len(slaves) == 0:
            self.sel = Signal()
        elif len(slaves) == 1:
            self.comb += master.connect(slaves.pop())
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
                If(status.first,
                    sel_ongoing.eq(self.sel)
                )
            self.comb += \
                If(status.first,
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
                cases[idx] = [master.connect(slave)]
            cases["default"] = [master.ready.eq(1)]
            self.comb += Case(sel, cases)

# Header -------------------------------------------------------------------------------------------

class HeaderField:
    def __init__(self, byte, offset, width):
        self.byte   = byte
        self.offset = offset
        self.width  = width


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
        if len(field) != width:
            raise ValueError("Width mismatch on " + name + " field")
        return field

    def encode(self, obj, signal):
        r = []
        for k, v in sorted(self.fields.items()):
            start = v.byte*8 + v.offset
            end = start + v.width
            field = self.get_field(obj, k, v.width)
            if self.swap_field_bytes:
                field = reverse_bytes(field)
            r.append(signal[start:end].eq(field))
        return r

    def decode(self, signal, obj):
        r = []
        for k, v in sorted(self.fields.items()):
            start = v.byte*8 + v.offset
            end = start + v.width
            field = self.get_field(obj, k, v.width)
            if self.swap_field_bytes:
                r.append(field.eq(reverse_bytes(signal[start:end])))
            else:
                r.append(field.eq(signal[start:end]))
        return r

# Packetizer ---------------------------------------------------------------------------------------

class Packetizer(Module):
    def __init__(self, sink_description, source_description, header):
        self.sink   =   sink = stream.Endpoint(sink_description)
        self.source = source = stream.Endpoint(source_description)
        self.header = Signal(header.length*8)

        # # #

        dw = len(self.sink.data)

        header_reg    = Signal(header.length*8, reset_less=True)
        header_words  = (header.length*8)//dw
        load          = Signal()
        shift         = Signal()
        counter       = Signal(max=max(header_words, 2))
        counter_reset = Signal()
        counter_ce    = Signal()
        self.sync += \
            If(counter_reset,
                counter.eq(0)
            ).Elif(counter_ce,
                counter.eq(counter + 1)
            )

        self.comb += header.encode(sink, self.header)
        if header_words == 1:
            self.sync += [
                If(load,
                    header_reg.eq(self.header)
                )
            ]
        else:
            self.sync += [
                If(load,
                    header_reg.eq(self.header)
                ).Elif(shift,
                    header_reg.eq(Cat(header_reg[dw:], Signal(dw)))
                )
            ]

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        if header_words == 1:
            idle_next_state = "COPY"
        else:
            idle_next_state = "SEND-HEADER"

        fsm.act("IDLE",
            sink.ready.eq(1),
            counter_reset.eq(1),
            If(sink.valid,
                sink.ready.eq(0),
                source.valid.eq(1),
                source.last.eq(0),
                source.data.eq(self.header[:dw]),
                If(source.valid & source.ready,
                    load.eq(1),
                    NextState(idle_next_state)
                )
            )
        )
        if header_words != 1:
            fsm.act("SEND-HEADER",
                source.valid.eq(1),
                source.last.eq(0),
                source.data.eq(header_reg[dw:2*dw]),
                If(source.valid & source.ready,
                    shift.eq(1),
                    counter_ce.eq(1),
                    If(counter == header_words-2,
                        NextState("COPY")
                    )
                )
            )
        if hasattr(sink, "error"):
            self.comb += source.error.eq(sink.error)
        fsm.act("COPY",
            source.valid.eq(sink.valid),
            source.last.eq(sink.last),
            source.data.eq(sink.data),
            If(source.valid & source.ready,
                sink.ready.eq(1),
                If(source.last,
                    NextState("IDLE")
                )
            )
        )

# Depacketizer -------------------------------------------------------------------------------------

class Depacketizer(Module):
    def __init__(self, sink_description, source_description, header):
        self.sink = sink = stream.Endpoint(sink_description)
        self.source = source = stream.Endpoint(source_description)
        self.header = Signal(header.length*8)

        # # #

        dw = len(sink.data)

        header_reg = Signal(header.length*8, reset_less=True)
        header_words = (header.length*8)//dw

        shift         = Signal()
        counter       = Signal(max=max(header_words, 2))
        counter_reset = Signal()
        counter_ce    = Signal()
        self.sync += \
            If(counter_reset,
                counter.eq(0)
            ).Elif(counter_ce,
                counter.eq(counter + 1)
            )

        if header_words == 1:
            self.sync += \
                If(shift,
                    header_reg.eq(sink.data)
                )
        else:
            self.sync += \
                If(shift,
                    header_reg.eq(Cat(header_reg[dw:], sink.data))
                )
        self.comb += self.header.eq(header_reg)

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        if header_words == 1:
            idle_next_state = "COPY"
        else:
            idle_next_state = "RECEIVE_HEADER"

        fsm.act("IDLE",
            sink.ready.eq(1),
            counter_reset.eq(1),
            If(sink.valid,
                shift.eq(1),
                NextState(idle_next_state)
            )
        )
        if header_words != 1:
            fsm.act("RECEIVE_HEADER",
                sink.ready.eq(1),
                If(sink.valid,
                    counter_ce.eq(1),
                    shift.eq(1),
                    If(counter == header_words-2,
                        NextState("COPY")
                    )
                )
            )
        no_payload = Signal()
        self.sync += \
            If(fsm.before_entering("COPY"),
                no_payload.eq(sink.last)
            )

        if hasattr(sink, "error"):
            self.comb += source.error.eq(sink.error)
        self.comb += [
            source.last.eq(sink.last | no_payload),
            source.data.eq(sink.data),
            header.decode(self.header, source)
        ]
        fsm.act("COPY",
            sink.ready.eq(source.ready),
            source.valid.eq(sink.valid | no_payload),
            If(source.valid & source.ready & source.last,
                NextState("IDLE")
            )
        )
