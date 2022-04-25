#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 Vamsi K Vytla <vkvytla@lbl.gov>
# SPDX-License-Identifier: BSD-2-Clause

from math import log2

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
        self.comb += If(endpoint.valid, self.last.eq(endpoint.last & endpoint.ready))
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
            self.sync += [
                If(status.first,
                    sel_ongoing.eq(self.sel)
                )
            ]
            self.comb += [
                If(status.first,
                    sel.eq(self.sel)
                ).Else(
                    sel.eq(sel_ongoing)
                )
            ]
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
        self.sink   = sink   = stream.Endpoint(sink_description)
        self.source = source = stream.Endpoint(source_description)
        self.header = Signal(header.length*8)

        # # #

        # Parameters.
        data_width      = len(self.sink.data)
        bytes_per_clk   = data_width//8
        header_words    = (header.length*8)//data_width
        header_leftover = header.length%bytes_per_clk
        aligned         = header_leftover == 0

        # Signals.
        sr       = Signal(header.length*8, reset_less=True)
        sr_load  = Signal()
        sr_shift = Signal()
        count    = Signal(max=max(header_words, 2))
        sink_d   = stream.Endpoint(sink_description)

        # Header Encode/Load/Shift.
        self.comb += header.encode(sink, self.header)
        self.sync += If(sr_load, sr.eq(self.header))
        if header_words != 1:
            self.sync += If(sr_shift, sr.eq(sr[data_width:]))

        # FSM.
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm_from_idle = Signal()
        fsm.act("IDLE",
            sink.ready.eq(1),
            NextValue(count, 1),
            If(sink.valid,
                sink.ready.eq(0),
                source.valid.eq(1),
                source.last.eq(0),
                source.data.eq(self.header[:data_width]),
                If(source.valid & source.ready,
                    sr_load.eq(1),
                    NextValue(fsm_from_idle, 1),
                    If(header_words == 1,
                        NextState("ALIGNED-DATA-COPY" if aligned else "UNALIGNED-DATA-COPY")
                    ).Else(
                        NextState("HEADER-SEND")
                    )
               )
            )
        )
        fsm.act("HEADER-SEND",
            source.valid.eq(1),
            source.last.eq(0),
            source.data.eq(sr[min(data_width, len(sr)-1):]),
            If(source.valid & source.ready,
                sr_shift.eq(1),
                If(count == (header_words - 1),
                    sr_shift.eq(0),
                    NextState("ALIGNED-DATA-COPY" if aligned else "UNALIGNED-DATA-COPY"),
                    NextValue(count, count + 1)
               ).Else(
                    NextValue(count, count + 1),
               )
            )
        )
        fsm.act("ALIGNED-DATA-COPY",
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
        if not aligned:
            header_offset_multiplier = 1 if header_words == 1 else 2
            self.sync += If(source.ready, sink_d.eq(sink))
            fsm.act("UNALIGNED-DATA-COPY",
                source.valid.eq(sink.valid | sink_d.last),
                source.last.eq(sink_d.last),
                If(fsm_from_idle,
                    source.data[:max(header_leftover*8, 1)].eq(sr[min(header_offset_multiplier*data_width, len(sr)-1):])
                ).Else(
                    source.data[:max(header_leftover*8, 1)].eq(sink_d.data[min((bytes_per_clk-header_leftover)*8, data_width-1):])
                ),
                source.data[header_leftover*8:].eq(sink.data),
                If(source.valid & source.ready,
                    sink.ready.eq(~source.last),
                    NextValue(fsm_from_idle, 0),
                    If(source.last,
                        NextState("IDLE")
                    )
                )
            )

        # Error.
        if hasattr(sink, "error") and hasattr(source, "error"):
            self.comb += source.error.eq(sink.error)

# Depacketizer -------------------------------------------------------------------------------------

class Depacketizer(Module):
    def __init__(self, sink_description, source_description, header):
        self.sink   = sink   = stream.Endpoint(sink_description)
        self.source = source = stream.Endpoint(source_description)
        self.header = Signal(header.length*8)

        # # #

        # Parameters.
        data_width      = len(sink.data)
        bytes_per_clk   = data_width//8
        header_words    = (header.length*8)//data_width
        header_leftover = header.length%bytes_per_clk
        aligned         = header_leftover == 0

        # Signals.
        sr                = Signal(header.length*8, reset_less=True)
        sr_shift          = Signal()
        sr_shift_leftover = Signal()
        count             = Signal(max=max(header_words, 2))
        sink_d            = stream.Endpoint(sink_description)

        # Header Shift/Decode.
        if (header_words) == 1 and (header_leftover == 0):
            self.sync += If(sr_shift, sr.eq(sink.data))
        else:
            self.sync += [
                If(sr_shift,          sr.eq(Cat(sr[bytes_per_clk*8:],   sink.data))),
                If(sr_shift_leftover, sr.eq(Cat(sr[header_leftover*8:], sink.data)))
            ]
        self.comb += self.header.eq(sr)
        self.comb += header.decode(self.header, source)

        # FSM.
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm_from_idle = Signal()
        fsm.act("IDLE",
            sink.ready.eq(1),
            NextValue(count, 1),
            If(sink.valid,
                sr_shift.eq(1),
                NextValue(fsm_from_idle, 1),
                If(header_words == 1,
                    NextState("ALIGNED-DATA-COPY" if aligned else "UNALIGNED-DATA-COPY"),
                ).Else(
                    NextState("HEADER-RECEIVE")
                )
            )
        )
        fsm.act("HEADER-RECEIVE",
            sink.ready.eq(1),
            If(sink.valid,
                NextValue(count, count + 1),
                sr_shift.eq(1),
                If(count == (header_words - 1),
                    NextState("ALIGNED-DATA-COPY" if aligned else "UNALIGNED-DATA-COPY"),
                    NextValue(count, count + 1),
                )
            )
        )
        fsm.act("ALIGNED-DATA-COPY",
            source.valid.eq(sink.valid | sink_d.last),
            source.last.eq(sink.last | sink_d.last),
            sink.ready.eq(source.ready),
            source.data.eq(sink.data),
            If(source.valid & source.ready,
               If(source.last,
                  NextState("IDLE")
               )
            )
        )

        if not aligned:
            self.sync += If(sink.valid & sink.ready, sink_d.eq(sink))
            fsm.act("UNALIGNED-DATA-COPY",
                source.valid.eq(sink.valid | sink_d.last),
                source.last.eq(sink.last | sink_d.last),
                sink.ready.eq(source.ready),
                source.data.eq(sink_d.data[header_leftover*8:]),
                source.data[min((bytes_per_clk-header_leftover)*8, data_width-1):].eq(sink.data),
                If(fsm_from_idle,
                    source.valid.eq(sink_d.last),
                    sink.ready.eq(1),
                    If(sink.valid,
                        NextValue(fsm_from_idle, 0),
                        sr_shift_leftover.eq(1),
                    )
                ),
                If(source.valid & source.ready,
                    If(source.last,
                        NextState("IDLE")
                    )
                )
            )

        # Error.
        if hasattr(sink, "error") and hasattr(source, "error"):
            self.comb += source.error.eq(sink.error)

# PacketFIFO ---------------------------------------------------------------------------------------

class PacketFIFO(Module):
    def __init__(self, layout, payload_depth, param_depth=None, buffered=False):
        self.sink   = sink   = stream.Endpoint(layout)
        self.source = source = stream.Endpoint(layout)

        # # #

        # Parameters.
        param_layout   = sink.description.param_layout
        payload_layout = sink.description.payload_layout
        if param_layout == []:
            param_layout = [("dummy", 1)]
        if param_depth is None:
            param_depth = payload_depth

        # Create the FIFOs.
        payload_description = stream.EndpointDescription(payload_layout=payload_layout)
        param_description   = stream.EndpointDescription(param_layout=param_layout)
        param_depth         = param_depth + 1 # +1 to allow dequeuing current while enqueuing next.
        self.submodules.payload_fifo = payload_fifo = stream.SyncFIFO(payload_description, payload_depth, buffered)
        self.submodules.param_fifo   = param_fifo   = stream.SyncFIFO(param_description,   param_depth,   buffered)

        # Connect Sink to FIFOs.
        self.comb += [
            sink.connect(param_fifo.sink,   keep=set([e[0] for e in param_layout])),
            sink.connect(payload_fifo.sink, keep=set([e[0] for e in payload_layout] + ["last"])),
            param_fifo.sink.valid.eq(sink.valid & sink.last),
            payload_fifo.sink.valid.eq(sink.valid & payload_fifo.sink.ready),
            sink.ready.eq(param_fifo.sink.ready & payload_fifo.sink.ready),
        ]

        # Connect FIFOs to Source.
        self.comb += [
            param_fifo.source.connect(source,   omit={"last",  "ready", "dummy"}),
            payload_fifo.source.connect(source, omit={"valid", "ready"}),
            param_fifo.source.ready.eq(  source.valid & source.last & source.ready),
            payload_fifo.source.ready.eq(source.valid &               source.ready),
        ]
