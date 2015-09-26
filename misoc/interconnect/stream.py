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
    def __init__(self, payload_layout, param_layout=[], packetized=False):
        self.payload_layout = payload_layout
        self.param_layout = param_layout
        self.packetized = packetized

    def get_full_layout(self):
        reserved = {"stb", "ack", "payload", "param", "sop", "eop", "description"}
        attributed = set()
        for f in self.payload_layout + self.param_layout:
            if f[0] in attributed:
                raise ValueError(f[0] + " already attributed in payload or param layout")
            if f[0] in reserved:
                raise ValueError(f[0] + " cannot be used in endpoint layout")
            attributed.add(f[0])

        full_layout = [
            ("payload", _make_m2s(self.payload_layout)),
            ("param", _make_m2s(self.param_layout)),
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
        try:
            return getattr(object.__getattribute__(self, "payload"), name)
        except:
            return getattr(object.__getattribute__(self, "param"), name)


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
        fifo_layout = [
            ("payload", description.payload_layout),
            # Note : Can be optimized by passing parameters
            #        in another fifo. We will only have one
            #        data per packet.
            ("param", description.param_layout)
        ]
        if description.packetized:
            fifo_layout += [("sop", 1), ("eop", 1)]

        self.submodules.fifo = fifo_class(fifo_layout, depth)

        self.comb += [
            self.sink.ack.eq(self.fifo.writable),
            self.fifo.we.eq(self.sink.stb),
            self.fifo.din.payload.eq(self.sink.payload),
            self.fifo.din.param.eq(self.sink.param),

            self.source.stb.eq(self.fifo.readable),
            self.source.payload.eq(self.fifo.dout.payload),
            self.source.param.eq(self.fifo.dout.param),
            self.fifo.re.eq(self.source.ack)
        ]
        if description.packetized:
            self.comb += [
                self.fifo.din.sop.eq(self.sink.sop),
                self.fifo.din.eop.eq(self.sink.eop),
                self.source.sop.eq(self.fifo.dout.sop),
                self.source.eop.eq(self.fifo.dout.eop)
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
