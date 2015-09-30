from migen import *
from migen.genlib.record import *
from migen.genlib import fifo


def _make_m2s(layout):
    r = []
    for f in layout:
        if isinstance(f[1], (int, tuple)):
            r.append((f[0], f[1], DIR_M_TO_S))
        else:
            r.append((f[0], _make_m2s(f[1])))
    return r


class EndpointDescription:
    def __init__(self, payload_layout, packetized=False):
        self.payload_layout = payload_layout
        self.packetized = packetized

    def get_full_layout(self):
        reserved = {"stb", "ack", "payload", "sop", "eop", "description"}
        attributed = set()
        for f in self.payload_layout:
            if f[0] in attributed:
                raise ValueError(f[0] + " already attributed in payload layout")
            if f[0] in reserved:
                raise ValueError(f[0] + " cannot be used in endpoint layout")
            attributed.add(f[0])

        full_layout = [
            ("payload", _make_m2s(self.payload_layout)),
            ("stb", 1, DIR_M_TO_S),
            ("ack", 1, DIR_S_TO_M)
        ]
        if self.packetized:
            full_layout += [
                ("sop", 1, DIR_M_TO_S),
                ("eop", 1, DIR_M_TO_S)
            ]
        return full_layout


class _Endpoint(Record):
    def __init__(self, description_or_layout):
        if isinstance(description_or_layout, EndpointDescription):
            self.description = description_or_layout
        else:
            self.description = EndpointDescription(description_or_layout)
        Record.__init__(self, self.description.get_full_layout())

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "payload"), name)


class Source(_Endpoint):
    def connect(self, sink):
        return Record.connect(self, sink)


class Sink(_Endpoint):
    def connect(self, source):
        return source.connect(self)


class _FIFOWrapper(Module):
    def __init__(self, fifo_class, layout, depth):
        self.sink = Sink(layout)
        self.source = Source(layout)
        self.busy = Signal()

        ###

        description = self.sink.description
        fifo_layout = [("payload", description.payload_layout)]
        if description.packetized:
            fifo_layout += [("sop", 1), ("eop", 1)]

        self.submodules.fifo = fifo_class(layout_len(fifo_layout), depth)
        fifo_in = Record(fifo_layout)
        fifo_out = Record(fifo_layout)
        self.comb += [
            self.fifo.din.eq(fifo_in.raw_bits()),
            fifo_out.raw_bits().eq(self.fifo.dout)
        ]

        self.comb += [
            self.sink.ack.eq(self.fifo.writable),
            self.fifo.we.eq(self.sink.stb),
            fifo_in.payload.eq(self.sink.payload),

            self.source.stb.eq(self.fifo.readable),
            self.source.payload.eq(fifo_out.payload),
            self.fifo.re.eq(self.source.ack)
        ]
        if description.packetized:
            self.comb += [
                fifo_in.sop.eq(self.sink.sop),
                fifo_in.eop.eq(self.sink.eop),
                self.source.sop.eq(fifo_out.sop),
                self.source.eop.eq(fifo_out.eop)
            ]


class SyncFIFO(_FIFOWrapper):
    def __init__(self, layout, depth, buffered=False):
        _FIFOWrapper.__init__(
            self,
            fifo.SyncFIFOBuffered if buffered else fifo.SyncFIFO,
            layout, depth)


class AsyncFIFO(_FIFOWrapper):
    def __init__(self, layout, depth):
        _FIFOWrapper.__init__(self, fifo.AsyncFIFO, layout, depth)


class Multiplexer(Module):
    def __init__(self, layout, n):
        self.source = Source(layout)
        sinks = []
        for i in range(n):
            sink = Sink(layout)
            setattr(self, "sink"+str(i), sink)
            sinks.append(sink)
        self.sel = Signal(max=n)

        # # #

        cases = {}
        for i, sink in enumerate(sinks):
            cases[i] = Record.connect(sink, self.source)
        self.comb += Case(self.sel, cases)


class Demultiplexer(Module):
    def __init__(self, layout, n):
        self.sink = Sink(layout)
        sources = []
        for i in range(n):
            source = Source(layout)
            setattr(self, "source"+str(i), source)
            sources.append(source)
        self.sel = Signal(max=n)
