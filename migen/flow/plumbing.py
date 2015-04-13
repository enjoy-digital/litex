from migen.fhdl.std import *
from migen.flow.actor import *
from migen.genlib.record import *
from migen.genlib.misc import optree


class Buffer(PipelinedActor):
    def __init__(self, layout):
        self.d = Sink(layout)
        self.q = Source(layout)
        PipelinedActor.__init__(self, 1)
        self.sync += \
            If(self.pipe_ce,
                self.q.payload.eq(self.d.payload),
                self.q.param.eq(self.d.param)
            )


class Combinator(Module):
    def __init__(self, layout, subrecords):
        self.source = Source(layout)
        sinks = []
        for n, r in enumerate(subrecords):
            s = Sink(layout_partial(layout, *r))
            setattr(self, "sink"+str(n), s)
            sinks.append(s)
        self.busy = Signal()

        ###

        self.comb += [
            self.busy.eq(0),
            self.source.stb.eq(optree("&", [sink.stb for sink in sinks]))
        ]
        self.comb += [sink.ack.eq(self.source.ack & self.source.stb) for sink in sinks]
        self.comb += [self.source.payload.eq(sink.payload) for sink in sinks]
        self.comb += [self.source.param.eq(sink.param) for sink in sinks]


class Splitter(Module):
    def __init__(self, layout, subrecords):
        self.sink = Sink(layout)
        sources = []
        for n, r in enumerate(subrecords):
            s = Source(layout_partial(layout, *r))
            setattr(self, "source"+str(n), s)
            sources.append(s)
        self.busy = Signal()

        ###

        self.comb += [source.payload.eq(self.sink.payload) for source in sources]
        self.comb += [source.param.eq(self.sink.param) for source in sources]
        already_acked = Signal(len(sources))
        self.sync += If(self.sink.stb,
                already_acked.eq(already_acked | Cat(*[s.ack for s in sources])),
                If(self.sink.ack, already_acked.eq(0))
            )
        self.comb += self.sink.ack.eq(optree("&",
                [s.ack | already_acked[n] for n, s in enumerate(sources)]))
        for n, s in enumerate(sources):
            self.comb += s.stb.eq(self.sink.stb & ~already_acked[n])


class Multiplexer(Module):
    def __init__(self, layout, n):
        self.source = Source(layout)
        sinks = []
        for i in range(n):
            sink = Sink(layout)
            setattr(self, "sink"+str(i), sink)
            sinks.append(sink)
        self.busy = Signal()
        self.sel = Signal(max=n)

        ###

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
        self.busy = Signal()
        self.sel = Signal(max=n)

        ###

        cases = {}
        for i, source in enumerate(sources):
            cases[i] = Record.connect(self.sink, source)
        self.comb += Case(self.sel, cases)

# Actors whose layout should be inferred from what their single sink is connected to.
layout_sink = {Buffer, Splitter}
# Actors whose layout should be inferred from what their single source is connected to.
layout_source = {Buffer, Combinator}
# All actors.
actors = layout_sink | layout_source
