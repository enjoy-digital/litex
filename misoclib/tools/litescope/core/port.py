from misoclib.tools.litescope.common import *


class LiteScopeTermUnit(Module):
    def __init__(self, dw):
        self.dw = dw
        self.sink = sink = Sink(data_layout(dw))
        self.source = source = Source(hit_layout())

        self.trig = Signal(dw)
        self.mask = Signal(dw)

        # # #

        self.comb += [
            source.stb.eq(sink.stb),
            source.hit.eq((sink.data & self.mask) == self.trig),
            sink.ack.eq(source.ack)
        ]


class LiteScopeTerm(LiteScopeTermUnit, AutoCSR):
    def __init__(self, dw):
        LiteScopeTermUnit.__init__(self, dw)
        self._trig = CSRStorage(dw)
        self._mask = CSRStorage(dw)

        # # #

        self.comb += [
            self.trig.eq(self._trig.storage),
            self.mask.eq(self._mask.storage)
        ]


class LiteScopeRangeDetectorUnit(Module):
    def __init__(self, dw):
        self.dw = dw
        self.sink = sink = Sink(data_layout(dw))
        self.source = source = Source(hit_layout())

        self.low = Signal(dw)
        self.high = Signal(dw)

        # # #

        self.comb += [
            source.stb.eq(sink.stb),
            source.hit.eq((sink.data >= self.low) & (sink.data <= self.high)),
            sink.ack.eq(source.ack)
        ]


class LiteScopeRangeDetector(LiteScopeRangeDetectorUnit, AutoCSR):
    def __init__(self, dw):
        LiteScopeRangeDetectorUnit.__init__(self, dw)
        self._low = CSRStorage(dw)
        self._high = CSRStorage(dw)

        # # #

        self.comb += [
            self.low.eq(self._low.storage),
            self.high.eq(self._high.storage)
        ]


class LiteScopeEdgeDetectorUnit(Module):
    def __init__(self, dw):
        self.dw = dw
        self.sink = sink = Sink(data_layout(dw))
        self.source = source = Source(hit_layout())

        self.rising_mask = Signal(dw)
        self.falling_mask = Signal(dw)
        self.both_mask = Signal(dw)

        # # #

        self.submodules.buffer = Buffer(self.sink.description)
        self.comb += Record.connect(self.sink, self.buffer.d)

        rising = Signal(dw)
        rising.eq(self.rising_mask & sink.data & ~self.buffer.q.data)

        falling = Signal(dw)
        falling.eq(self.falling_mask & ~sink.data & self.buffer.q.data)

        both = Signal(dw)
        both.eq(self.both_mask & (rising | falling))

        self.comb += [
            source.stb.eq(sink.stb & self.buffer.q.stb),
            self.buffer.q.ack.eq(source.ack),
            source.hit.eq((rising | falling | both) != 0)
        ]


class LiteScopeEdgeDetector(LiteScopeEdgeDetectorUnit, AutoCSR):
    def __init__(self, dw):
        LiteScopeEdgeDetectorUnit.__init__(self, dw)
        self._rising = CSRStorage(dw)
        self._falling = CSRStorage(dw)
        self._both = CSRStorage(dw)

        # # #

        self.comb += [
            self.rising_mask.eq(self._rising.storage),
            self.falling_mask.eq(self._falling.storage),
            self.both_mask.eq(self._both.storage)
        ]
