from migen import *

from litex.soc.interconnect import stream

# AvalonST to/from Native --------------------------------------------------------------------------

class Native2AvalonST(Module):
    def __init__(self, layout, latency=2):
        self.sink = sink = stream.Endpoint(layout)
        self.source = source = stream.Endpoint(layout)

        # # #

        _from = sink
        for n in range(latency):
            _to = stream.Endpoint(layout)
            self.sync += _from.connect(_to, omit={"ready"})
            if n == 0:
                self.sync += _to.valid.eq(sink.valid & source.ready)
            _from = _to
        self.comb += _to.connect(source, omit={"ready"})
        self.comb += sink.ready.eq(source.ready)


class AvalonST2Native(Module):
    def __init__(self, layout, latency=2):
        self.sink = sink = stream.Endpoint(layout)
        self.source = source = stream.Endpoint(layout)

        # # #

        buf = stream.SyncFIFO(layout, max(latency, 4))
        self.submodules += buf
        self.comb += [
            sink.connect(buf.sink, omit={"ready"}),
            sink.ready.eq(source.ready),
            buf.source.connect(source)
        ]
