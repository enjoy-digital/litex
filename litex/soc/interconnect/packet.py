#
# This file is part of LiteX.
#
# Copyright (c) 2015-2024 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 Vamsi K Vytla <vkvytla@lbl.gov>
# SPDX-License-Identifier: BSD-2-Clause

from math import log2

from migen import *
from migen.genlib.roundrobin import *

from litex.gen import *

from litex.soc.interconnect import stream

# Status -------------------------------------------------------------------------------------------

class Status(LiteXModule):
    def __init__(self, endpoint):
        self.first   = Signal(reset=1)
        self.last    = Signal()
        self.ongoing = Signal()

        ongoing = Signal()
        # Derive packet state from accepted beats.
        self.comb += self.last.eq(endpoint.valid & endpoint.last & endpoint.ready)
        self.comb += self.ongoing.eq((endpoint.valid | ongoing) & ~self.last)
        self.sync += [
            ongoing.eq(self.ongoing),
            If(self.last,
                self.first.eq(1)
            ).Elif(endpoint.valid & endpoint.ready,
                self.first.eq(0)
            )
        ]

# Arbiter ------------------------------------------------------------------------------------------

class Arbiter(LiteXModule):
    def __init__(self, masters, slave, **kwargs):
        if len(masters) == 0:
            pass
        elif len(masters) == 1:
            self.grant = Signal()
            self.comb += masters.pop().connect(slave, **kwargs)
        else:
            self.rr = RoundRobin(len(masters))
            self.grant = self.rr.grant
            cases = {}
            for i, master in enumerate(masters):
                status = Status(master)
                self.submodules += status
                self.comb += self.rr.request[i].eq(status.ongoing)
                cases[i] = [master.connect(slave, **kwargs)]
            self.comb += Case(self.grant, cases)

# Dispatcher ---------------------------------------------------------------------------------------

class Dispatcher(LiteXModule):
    def __init__(self, master, slaves, one_hot=False, **kwargs):
        if len(slaves) == 0:
            self.sel = Signal()
        elif len(slaves) == 1 and not one_hot:
            self.comb += master.connect(slaves.pop(), **kwargs)
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
            sel_locked = Signal()
            # Hold the route from first beat to packet completion.
            self.sync += [
                If(status.last,
                    sel_locked.eq(0)
                ).Elif(status.first & master.valid & ~sel_locked,
                    sel_ongoing.eq(self.sel),
                    sel_locked.eq(1)
                )
            ]
            self.comb += [
                If(~sel_locked,
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
                cases[idx] = [master.connect(slave, **kwargs)]
            cases["default"] = [master.ready.eq(1)]
            self.comb += Case(sel, cases)

# Header -------------------------------------------------------------------------------------------

class HeaderField:
    def __init__(self, byte=0, offset=0, width=1):
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

    def encode(self, obj, signal, shift=0):
        r = []
        for k, v in sorted(self.fields.items()):
            start = shift*8 + v.byte*8 + v.offset
            end = start + v.width
            field = self.get_field(obj, k, v.width)
            if self.swap_field_bytes:
                field = reverse_bytes(field)
            r.append(signal[start:end].eq(field))
        return r

    def decode(self, signal, obj, shift=0):
        r = []
        for k, v in sorted(self.fields.items()):
            start = shift*8 + v.byte*8 + v.offset
            end = start + v.width
            field = self.get_field(obj, k, v.width)
            if self.swap_field_bytes:
                r.append(field.eq(reverse_bytes(signal[start:end])))
            else:
                r.append(field.eq(signal[start:end]))
        return r

# Packetizer ---------------------------------------------------------------------------------------

class Packetizer(LiteXModule):
    """Prepend a header to a packet stream.

    Headers may span words or share a word with payload. Byte qualifiers (be or keep) move
    with data; a final zero-mask input beat represents a header-only packet. Without a
    qualifier, unaligned headers always add a flush word. With ``with_first=True``, discard
    beats outside a packet until ``first`` is asserted.
    """
    def __init__(self, sink_description, source_description, header, with_first=False):
        self.sink   = sink   = stream.Endpoint(sink_description)
        self.source = source = stream.Endpoint(source_description)
        self.header = Signal(header.length*8)

        # # #

        data_width      = len(sink.data)
        bytes_per_clk   = data_width//8
        header_words    = header.length//bytes_per_clk
        header_leftover = header.length%bytes_per_clk
        aligned         = header_leftover == 0
        sink_be_name    = stream.byte_enable_name(sink)
        source_be_name  = stream.byte_enable_name(source)
        with_be         = sink_be_name is not None and source_be_name is not None
        with_error      = hasattr(sink, "error") and hasattr(source, "error")
        byte_errors     = with_error and with_be and len(sink.error) == bytes_per_clk
        if (sink_be_name is None) != (source_be_name is None):
            raise ValueError("Packet helpers require byte qualifiers on both endpoints or neither.")
        if header.length <= 0:
            raise ValueError("Packetizer requires a nonempty header.")

        self.comb += header.encode(sink, self.header)
        full_be   = (1 << bytes_per_clk) - 1
        sink_be   = getattr(sink, sink_be_name) if with_be else C(full_be, bytes_per_clk)
        source_be = Signal(bytes_per_clk, reset=full_be)
        if with_be:
            self.comb += getattr(source, source_be_name).eq(source_be)
        empty = sink.last & (sink_be == 0) if with_be else 0

        # The first input beat is held until its payload is consumed. Its header parameters
        # therefore remain stable throughout header emission; no separate header register is needed.
        header_beats = header_words + (header_leftover != 0)
        count        = Signal(max=max(header_beats, 2))
        last_header  = count == (header_beats - 1)
        header_cases = {
            i : source.data.eq(self.header[i*data_width:(i + 1)*data_width])
            for i in range(header_words)
        }

        self.fsm = fsm = FSM(reset_state="IDLE")
        if aligned:
            header_last  = empty
            header_ready = empty
            header_be    = C(full_be, bytes_per_clk)
            if with_error:
                if byte_errors:
                    self.comb += If(fsm.ongoing("COPY"), source.error.eq(sink.error))
                else:
                    self.comb += source.error.eq(sink.error)
        else:
            # Retain the accepted payload's tail for the next word. Only the FSM/flush
            # state needs reset: saved data and masks are read after an accepted beat.
            leftover_bits = 8*header_leftover
            tail_bits     = data_width - leftover_bits
            sink_d_data   = Signal(data_width, reset_less=True)
            sink_d_be     = Signal(bytes_per_clk, reset_less=True)
            flush         = Signal()
            wrap = (sink_be[bytes_per_clk-header_leftover:] != 0) if with_be else 1
            header_last  = sink.last & ~wrap if with_be else 0
            header_ready = 1
            header_be    = Cat(C((1 << header_leftover) - 1, header_leftover),
                sink_be[:bytes_per_clk-header_leftover])
            header_cases[header_words] = source.data.eq(Cat(
                self.header[header_words*data_width:], sink.data[:tail_bits]))

            accepted = sink.valid & sink.ready
            if with_first:
                accepted = accepted & (sink.first | (count != 0) | ~fsm.ongoing("IDLE"))
            self.sync += [
                If(accepted,
                    sink_d_data.eq(sink.data),
                    sink_d_be.eq(sink_be),
                    flush.eq(sink.last & wrap),
                ),
                If(fsm.ongoing("COPY") & flush & source.ready, flush.eq(0)),
            ]
            if with_error:
                sink_d_error = Signal.like(sink.error, reset_less=True)
                self.sync += If(accepted, sink_d_error.eq(sink.error))
                if byte_errors:
                    self.comb += If(fsm.ongoing("IDLE"),
                        If(last_header,
                            source.error.eq(Cat(C(0, header_leftover), sink.error[:bytes_per_clk-header_leftover])),
                        ),
                    ).Else(
                        source.error.eq(Cat(sink_d_error[bytes_per_clk-header_leftover:],
                            Mux(flush, 0, sink.error[:bytes_per_clk-header_leftover]))),
                    )
                else:
                    self.comb += source.error.eq(Mux(flush, sink_d_error, sink.error))

        fsm.act("IDLE",
            sink.ready.eq(count == 0),
            Case(count, header_cases),
            If(last_header, source_be.eq(header_be)),
            If(sink.valid & ((count != 0) | sink.first if with_first else 1),
                source.valid.eq(1),
                source.first.eq(count == 0),
                source.last.eq(last_header & header_last),
                sink.ready.eq(last_header & header_ready & source.ready),
                If(source.ready,
                    If(last_header,
                        NextValue(count, 0),
                        If(~source.last, NextState("COPY")),
                    ).Else(
                        NextValue(count, count + 1),
                    ),
                ),
            ),
        )
        if aligned:
            fsm.act("COPY",
                sink.connect(source, keep={"valid", "ready", "last", "data"}),
                source_be.eq(sink_be),
                If(source.valid & source.ready & source.last, NextState("IDLE")),
            )
        else:
            fsm.act("COPY",
                source.valid.eq(sink.valid | flush),
                source.last.eq(flush | (sink.last & ~wrap) if with_be else flush),
                source.data.eq(Cat(sink_d_data[tail_bits:], Mux(flush, 0, sink.data[:tail_bits]))),
                source_be.eq(Cat(sink_d_be[bytes_per_clk-header_leftover:],
                    Mux(flush, 0, sink_be[:bytes_per_clk-header_leftover]))),
                If(source.valid & source.ready,
                    sink.ready.eq(~flush),
                    If(source.last, NextState("IDLE")),
                ),
            )

# Depacketizer -------------------------------------------------------------------------------------

class Depacketizer(LiteXModule):
    """Strip a header from a packet stream.

    The header is decoded into the source's param fields, then the payload is copied. When the
    header length is not a multiple of the data width (unaligned), the payload is shifted down by
    header_leftover bytes: each source word combines the tail of the previous sink word with the
    head of the current one, and the packet's last bytes can require an extra source word.

    With be on sink and source, the extra word is only emitted when the last valid bytes are in
    the tail of the last sink word and be is adjusted, so the packet is byte-exact. Without
    be, the tail of the last sink word is dropped, except for a single-word payload (whose
    tail is the whole payload), matching the Packetizer's whole-word transmission.

    Headers shorter than a word share the first beat with payload. Packets ending within the
    header (truncated), including header-only packets, are dropped.
    """
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
        sink_be_name    = stream.byte_enable_name(sink)
        source_be_name  = stream.byte_enable_name(source)
        with_be         = sink_be_name is not None and source_be_name is not None
        if (sink_be_name is None) != (source_be_name is None):
            raise ValueError("Packet helpers require byte qualifiers on both endpoints or neither.")
        with_error      = hasattr(sink, "error") and hasattr(source, "error")
        if header.length <= 0:
            raise ValueError("Depacketizer requires a nonempty header.")

        # Signals.
        sr                = Signal(header.length*8, reset_less=True)
        sr_shift          = Signal()
        sr_shift_leftover = Signal()
        count             = Signal(max=max(header_words, 2))
        data_copy_first   = Signal()

        # Header Shift/Decode.
        if header_words == 0 or (header_words == 1 and aligned):
            self.sync += If(sr_shift, sr.eq(sink.data))
        else:
            self.sync += [
                If(sr_shift,          sr.eq(Cat(sr[bytes_per_clk*8:],   sink.data))),
                If(sr_shift_leftover, sr.eq(Cat(sr[header_leftover*8:], sink.data)))
            ]
        self.comb += self.header.eq(sr)
        self.comb += header.decode(self.header, source)

        # Byte enables accompany the data on every beat. Header bytes are always valid.
        sink_be   = Signal(bytes_per_clk)
        source_be = Signal(bytes_per_clk, reset=(1 << bytes_per_clk) - 1)
        be_copy   = []
        if with_be:
            self.comb += [sink_be.eq(getattr(sink, sink_be_name)), getattr(source, source_be_name).eq(source_be)]
            be_copy = [source_be.eq(sink_be)]

        # FSM.
        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm_from_idle = Signal()
        # A short header may leave payload in the very first beat. Longer headers never do.
        first_has_payload = (sink_be[header_leftover:] != 0) if with_be else 1
        if header_words != 0:
            first_has_payload = 0
        fsm.act("IDLE",
            sink.ready.eq(1),
            NextValue(count, 1),
            If(sink.valid,
                sr_shift.eq(1),
                NextValue(fsm_from_idle, header_words != 0),
                NextValue(data_copy_first, 1),
                If(header_words <= 1,
                    NextState("ALIGNED-DATA-COPY" if aligned else "UNALIGNED-DATA-COPY"),
                ).Else(
                    NextState("HEADER-RECEIVE")
                ),
                # Drop packets that end within the header (header-only/truncated): falling through
                # would emit the *next* packet's header as payload of the previous one.
                If(sink.last & ~first_has_payload, NextState("IDLE")),
            )
        )
        fsm.act("HEADER-RECEIVE",
            sink.ready.eq(1),
            If(sink.valid,
                NextValue(count, count + 1),
                sr_shift.eq(1),
                If(count == (header_words - 1),
                    NextValue(data_copy_first, 1),
                    NextState("ALIGNED-DATA-COPY" if aligned else "UNALIGNED-DATA-COPY"),
                    NextValue(count, count + 1),
                ),
                # Drop packets that end within the header (see IDLE).
                If(sink.last, NextState("IDLE")),
            )
        )
        fsm.act("ALIGNED-DATA-COPY",
            source.valid.eq(sink.valid),
            source.first.eq(data_copy_first),
            source.last.eq(sink.last),
            sink.ready.eq(source.ready),
            source.data.eq(sink.data),
            *be_copy,
            If(source.valid & source.ready,
               NextValue(data_copy_first, 0),
               NextValue(fsm_from_idle, 0),
               If(source.last,
                  NextState("IDLE")
               )
            )
        )
        if aligned:
            if with_error:
                self.comb += source.error.eq(sink.error)
        else:
            # The payload is shifted down by header_leftover bytes: each source word combines the
            # tail of the previous sink word (sink_d) with the head of the current one. The last
            # sink word's tail needs an extra source word (flush) when it holds payload: with
            # be, when the last valid byte is at or beyond the leftover; without, only for a
            # single-word payload (otherwise the tail is dropped, matching the Packetizer's
            # whole-word transmission).
            sink_d_data  = Signal(data_width)
            sink_d_be    = Signal(bytes_per_clk)
            flush        = Signal()
            flush_needed = Signal()
            if with_be:
                self.comb += flush_needed.eq(sink_be[header_leftover:] != 0)
            else:
                self.comb += flush_needed.eq(fsm_from_idle | (fsm.ongoing("IDLE") if header_words == 0 else 0))

            # Capture the accepted sink word (header words included, the flush is only recorded on
            # a payload word). The flush is cleared once the extra word has been accepted.
            sink_d_capture = [
                sink_d_data.eq(sink.data),
                flush.eq(sink.last & flush_needed &
                    (fsm.ongoing("UNALIGNED-DATA-COPY") | (fsm.ongoing("IDLE") if header_words == 0 else 0))),
            ]
            be_shift = []
            from_idle_drop = []
            if with_be:
                sink_d_capture += [sink_d_be.eq(sink_be)]
                be_shift = [
                    source_be.eq(Cat(
                        sink_d_be[header_leftover:],
                        Mux(flush, 0, sink_be[:header_leftover]),
                    ))
                ]
                # First payload word ending without payload in its tail: truncated, drop (without
                # be the tail always holds payload).
                from_idle_drop  = [If(sink.last & ~flush_needed, NextState("IDLE"))]
            if with_error:
                sink_d_error    = Signal.like(sink.error)
                sink_d_capture += [sink_d_error.eq(sink.error)]
                if with_be and len(sink.error) == bytes_per_clk:
                    self.comb += source.error.eq(Cat(
                        sink_d_error[header_leftover:],
                        Mux(flush, 0, sink.error[:header_leftover]),
                    ))
                else:
                    self.comb += source.error.eq(Mux(flush, sink_d_error, sink.error))
            self.sync += [
                If(sink.valid & sink.ready, *sink_d_capture),
                If(flush & source.ready,    flush.eq(0)),
            ]

            # Source word: low bytes from the previous sink word's tail, high bytes from the current
            # sink word's head (undefined on the flush word).
            leftover_bits = header_leftover*8
            tail_bits     = (bytes_per_clk - header_leftover)*8
            fsm.act("UNALIGNED-DATA-COPY",
                source.valid.eq(sink.valid | flush),
                source.first.eq(data_copy_first & source.valid),
                source.last.eq(flush | (sink.last & ~flush_needed)),
                sink.ready.eq(source.ready & ~flush),
                source.data.eq(sink_d_data[leftover_bits:]),
                source.data[tail_bits:].eq(Mux(flush, 0, sink.data)),
                *be_shift,
                If(fsm_from_idle,
                    # First payload word: header leftover + payload head, nothing to output yet.
                    source.valid.eq(0),
                    sink.ready.eq(1),
                    If(sink.valid,
                        NextValue(fsm_from_idle, 0),
                        sr_shift_leftover.eq(1),
                        *from_idle_drop,
                    )
                ),
                If(source.valid & source.ready,
                    NextValue(data_copy_first, 0),
                    NextValue(fsm_from_idle, 0),
                    If(source.last,
                        NextState("IDLE")
                    )
                )
            )

# PacketFIFO ---------------------------------------------------------------------------------------

class PacketFIFO(LiteXModule):
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
        # Allow param dequeue/enqueue overlap on packet boundaries.
        param_depth         = param_depth + 1 # +1 to allow dequeuing current while enqueuing next.
        self.payload_fifo = payload_fifo = stream.SyncFIFO(payload_description, payload_depth, buffered)
        self.param_fifo   = param_fifo   = stream.SyncFIFO(param_description,   param_depth,   buffered)

        # Connect Sink to FIFOs.
        self.comb += [
            sink.connect(param_fifo.sink,   keep=set([e[0] for e in param_layout])),
            sink.connect(payload_fifo.sink, keep=set([e[0] for e in payload_layout] + ["first", "last"])),
            # Qualify with payload_fifo.sink.ready: with the last beat stalled on a full payload
            # FIFO, the params would otherwise be (re-)enqueued every cycle, later replaying as
            # phantom packets with stale payload.
            param_fifo.sink.valid.eq(sink.valid & sink.last & payload_fifo.sink.ready),
            payload_fifo.sink.valid.eq(sink.valid & param_fifo.sink.ready),
            sink.ready.eq(param_fifo.sink.ready & payload_fifo.sink.ready),
        ]

        # Connect FIFOs to Source.
        self.comb += [
            param_fifo.source.connect(source,   omit={"last",  "ready", "dummy"}),
            payload_fifo.source.connect(source, omit={"valid", "ready"}),
            param_fifo.source.ready.eq(  source.valid & source.last & source.ready),
            payload_fifo.source.ready.eq(source.valid &               source.ready),
        ]
