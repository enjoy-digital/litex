from litex.gen import *
from litex.gen.genlib.record import *
from litex.gen.genlib import fifo

(DIR_SINK, DIR_SOURCE) = range(2)

def _make_m2s(layout):
    r = []
    for f in layout:
        if isinstance(f[1], (int, tuple)):
            r.append((f[0], f[1], DIR_M_TO_S))
        else:
            r.append((f[0], _make_m2s(f[1])))
    return r


class EndpointDescription:
    def __init__(self, payload_layout, param_layout=[]):
        self.payload_layout = payload_layout
        self.param_layout = param_layout

    def get_full_layout(self):
        reserved = {"stb", "ack", "payload", "param", "eop", "description"}
        attributed = set()
        for f in self.payload_layout + self.param_layout:
            if f[0] in attributed:
                raise ValueError(f[0] + " already attributed in payload or param layout")
            if f[0] in reserved:
                raise ValueError(f[0] + " cannot be used in endpoint layout")
            attributed.add(f[0])

        full_layout = [
            ("stb", 1, DIR_M_TO_S),
            ("ack", 1, DIR_S_TO_M),
            ("eop", 1, DIR_M_TO_S),
            ("payload", _make_m2s(self.payload_layout)),
            ("param", _make_m2s(self.param_layout))
        ]
        return full_layout


class Endpoint(Record):
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


class _FIFOWrapper(Module):
    def __init__(self, fifo_class, layout, depth):
        self.sink = Endpoint(layout)
        self.source = Endpoint(layout)

        # # #

        description = self.sink.description
        fifo_layout = [("payload", description.payload_layout),
                       ("param", description.param_layout),
                       ("eop", 1)]

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
            fifo_in.eop.eq(self.sink.eop),
            fifo_in.payload.eq(self.sink.payload),
            fifo_in.param.eq(self.sink.param),

            self.source.stb.eq(self.fifo.readable),
            self.source.eop.eq(fifo_out.eop),
            self.source.payload.eq(fifo_out.payload),
            self.source.param.eq(fifo_out.param),
            self.fifo.re.eq(self.source.ack)
        ]


class SyncFIFO(_FIFOWrapper):
    def __init__(self, layout, depth, buffered=False):
        _FIFOWrapper.__init__(
            self,
            fifo.SyncFIFOBuffered if buffered else fifo.SyncFIFO,
            layout, depth)
        self.level = self.fifo.level


class AsyncFIFO(_FIFOWrapper):
    def __init__(self, layout, depth):
        _FIFOWrapper.__init__(self, fifo.AsyncFIFO, layout, depth)


class Multiplexer(Module):
    def __init__(self, layout, n):
        self.source = Endpoint(layout)
        sinks = []
        for i in range(n):
            sink = Endpoint(layout)
            setattr(self, "sink"+str(i), sink)
            sinks.append(sink)
        self.sel = Signal(max=n)

        # # #

        cases = {}
        for i, sink in enumerate(sinks):
            cases[i] = sink.connect(self.source)
        self.comb += Case(self.sel, cases)


class Demultiplexer(Module):
    def __init__(self, layout, n):
        self.sink = Endpoint(layout)
        sources = []
        for i in range(n):
            source = Endpoint(layout)
            setattr(self, "source"+str(i), source)
            sources.append(source)
        self.sel = Signal(max=n)

        # # #

        cases = {}
        for i, source in enumerate(sources):
            cases[i] = self.sink.connect(source)
        self.comb += Case(self.sel, cases)


class _UpConverter(Module):
    def __init__(self, nbits_from, nbits_to, ratio, reverse):
        self.sink = sink = Endpoint([("data", nbits_from)])
        self.source = source = Endpoint([("data", nbits_to),
                                         ("valid_token_count", bits_for(ratio))])
        self.latency = 1

        # # #

        # control path
        demux = Signal(max=ratio)
        load_part = Signal()
        strobe_all = Signal()
        self.comb += [
            sink.ack.eq(~strobe_all | source.ack),
            source.stb.eq(strobe_all),
            load_part.eq(sink.stb & sink.ack)
        ]

        demux_last = ((demux == (ratio - 1)) | sink.eop)

        self.sync += [
            If(source.ack, strobe_all.eq(0)),
            If(load_part,
                If(demux_last,
                    demux.eq(0),
                    strobe_all.eq(1)
                ).Else(
                    demux.eq(demux + 1)
                )
            ),
            If(source.stb & source.ack,
                source.eop.eq(sink.eop),
            ).Elif(sink.stb & sink.ack,
                source.eop.eq(sink.eop | source.eop)
            )
        ]

        # data path
        cases = {}
        for i in range(ratio):
            n = ratio-i-1 if reverse else i
            cases[i] = source.data[n*nbits_from:(n+1)*nbits_from].eq(sink.data)
        self.sync += If(load_part, Case(demux, cases))

        # valid token count
        self.sync += If(load_part, source.valid_token_count.eq(demux + 1))


class _DownConverter(Module):
    def __init__(self, nbits_from, nbits_to, ratio, reverse):
        self.sink = sink = Endpoint([("data", nbits_from)])
        self.source = source = Endpoint([("data", nbits_to),
                                         ("valid_token_count", 1)])
        self.latency = 0

        # # #

        # control path
        mux = Signal(max=ratio)
        last = Signal()
        self.comb += [
            last.eq(mux == (ratio-1)),
            source.stb.eq(sink.stb),
            source.eop.eq(sink.eop & last),
            sink.ack.eq(last & source.ack)
        ]
        self.sync += \
            If(source.stb & source.ack,
                If(last,
                    mux.eq(0)
                ).Else(
                    mux.eq(mux + 1)
                )
            )

        # data path
        cases = {}
        for i in range(ratio):
            n = ratio-i-1 if reverse else i
            cases[i] = source.data.eq(sink.data[n*nbits_to:(n+1)*nbits_to])
        self.comb += Case(mux, cases).makedefault()

        # valid token count
        self.comb += source.valid_token_count.eq(last)


class _IdentityConverter(Module):
    def __init__(self, nbits_from, nbits_to, ratio, reverse):
        self.sink = sink = Endpoint([("data", nbits_from)])
        self.source = source = Endpoint([("data", nbits_to),
                                         ("valid_token_count", 1)])
        self.latency = 0

        # # #

        self.comb += [
            sink.connect(source),
            source.valid_token_count.eq(1)
        ]


def _get_converter_ratio(nbits_from, nbits_to):
    if nbits_from > nbits_to:
        converter_cls = _DownConverter
        if nbits_from % nbits_to:
            raise ValueError("Ratio must be an int")
        ratio = nbits_from//nbits_to
    elif nbits_from < nbits_to:
        converter_cls = _UpConverter
        if nbits_to % nbits_from:
            raise ValueError("Ratio must be an int")
        ratio = nbits_to//nbits_from
    else:
        converter_cls = _IdentityConverter
        ratio = 1

    return converter_cls, ratio


class Converter(Module):
    def __init__(self, nbits_from, nbits_to, reverse=False,
        report_valid_token_count=False):
        self.cls, self.ratio = _get_converter_ratio(nbits_from, nbits_to)

        # # #

        converter = self.cls(nbits_from, nbits_to, self.ratio, reverse)
        self.submodules += converter
        self.latency = converter.latency

        self.sink = converter.sink
        if report_valid_token_count:
            self.source = converter.source
        else:
            self.source = Endpoint([("data", nbits_to)])
            self.comb += converter.source.connect(self.source,
                            leave_out=set(["valid_token_count"]))


class StrideConverter(Module):
    def __init__(self, description_from, description_to, reverse=False):
        self.sink = sink = Endpoint(description_from)
        self.source = source = Endpoint(description_to)

        # # #

        nbits_from = len(sink.payload.raw_bits())
        nbits_to = len(source.payload.raw_bits())

        converter = Converter(nbits_from, nbits_to, reverse)
        self.submodules += converter

        # cast sink to converter.sink (user fields --> raw bits)
        self.comb += [
            converter.sink.stb.eq(sink.stb),
            converter.sink.eop.eq(sink.eop),
            sink.ack.eq(converter.sink.ack)
        ]
        if converter.cls == _DownConverter:
            ratio = converter.ratio
            for i in range(ratio):
                j = 0
                for name, width in source.description.payload_layout:
                    src = getattr(sink, name)[i*width:(i+1)*width]
                    dst = converter.sink.data[i*nbits_to+j:i*nbits_to+j+width]
                    self.comb += dst.eq(src)
                    j += width
        else:
            self.comb += converter.sink.data.eq(sink.payload.raw_bits())


        # cast converter.source to source (raw bits --> user fields)
        self.comb += [
            source.stb.eq(converter.source.stb),
            source.eop.eq(converter.source.eop),
            converter.source.ack.eq(source.ack)
        ]
        if converter.cls == _UpConverter:
            ratio = converter.ratio
            for i in range(ratio):
                j = 0
                for name, width in sink.description.payload_layout:
                    src = converter.source.data[i*nbits_from+j:i*nbits_from+j+width]
                    dst = getattr(source, name)[i*width:(i+1)*width]
                    self.comb += dst.eq(src)
                    j += width
        else:
            self.comb += source.payload.raw_bits().eq(converter.source.data)

        # connect params
        if converter.latency == 0:
            self.comb += source.param.eq(sink.param)
        elif converter.latency == 1:
            self.sync += source.param.eq(sink.param)
        else:
            raise ValueError


# TODO: clean up code below
# XXX

from copy import copy
from litex.gen.util.misc import xdir

def _rawbits_layout(l):
    if isinstance(l, int):
        return [("rawbits", l)]
    else:
        return l

def pack_layout(l, n):
    return [("chunk"+str(i), l) for i in range(n)]

def get_endpoints(obj, filt=Endpoint):
    if hasattr(obj, "get_endpoints") and callable(obj.get_endpoints):
        return obj.get_endpoints(filt)
    r = dict()
    for k, v in xdir(obj, True):
        if isinstance(v, filt):
            r[k] = v
    return r

def get_single_ep(obj, filt):
    eps = get_endpoints(obj, filt)
    if len(eps) != 1:
        raise ValueError("More than one endpoint")
    return list(eps.items())[0]


class BinaryActor(Module):
    def __init__(self, *args, **kwargs):
        self.build_binary_control(self.sink, self.source, *args, **kwargs)

    def build_binary_control(self, sink, source):
        raise NotImplementedError("Binary actor classes must overload build_binary_control_fragment")


class CombinatorialActor(BinaryActor):
    def build_binary_control(self, sink, source):
        self.comb += [
            source.stb.eq(sink.stb),
            source.eop.eq(sink.eop),
            sink.ack.eq(source.ack),
        ]


class PipelinedActor(BinaryActor):
    def __init__(self, latency):
        self.pipe_ce = Signal()
        BinaryActor.__init__(self, latency)

    def build_binary_control(self, sink, source, latency):
        valid = sink.stb
        for i in range(latency):
            valid_n = Signal()
            self.sync += If(self.pipe_ce, valid_n.eq(valid))
            valid = valid_n

        self.comb += [
            self.pipe_ce.eq(source.ack | ~valid),
            sink.ack.eq(self.pipe_ce),
            source.stb.eq(valid)
        ]
        eop = sink.stb & sink.eop
        for i in range(latency):
            eop_n = Signal()
            self.sync += \
                If(self.pipe_ce,
                    eop_n.eq(eop)
                )
            eop = eop_n
        self.comb += source.eop.eq(eop)


class Buffer(PipelinedActor):
    def __init__(self, layout):
        self.sink = Endpoint(layout)
        self.source = Endpoint(layout)
        PipelinedActor.__init__(self, 1)
        self.sync += \
            If(self.pipe_ce,
                self.source.payload.eq(self.sink.payload),
                self.source.param.eq(self.sink.param)
            )


class Cast(CombinatorialActor):
    def __init__(self, layout_from, layout_to, reverse_from=False, reverse_to=False):
        self.sink = Endpoint(_rawbits_layout(layout_from))
        self.source = Endpoint(_rawbits_layout(layout_to))
        CombinatorialActor.__init__(self)

        # # #

        sigs_from = self.sink.payload.flatten()
        if reverse_from:
            sigs_from = list(reversed(sigs_from))
        sigs_to = self.source.payload.flatten()
        if reverse_to:
            sigs_to = list(reversed(sigs_to))
        if sum(len(s) for s in sigs_from) != sum(len(s) for s in sigs_to):
            raise TypeError
        self.comb += Cat(*sigs_to).eq(Cat(*sigs_from))


class Unpack(Module):
    def __init__(self, n, layout_to, reverse=False):
        self.source = source = Endpoint(layout_to)
        description_from = copy(source.description)
        description_from.payload_layout = pack_layout(description_from.payload_layout, n)
        self.sink = sink = Endpoint(description_from)

        # # #

        mux = Signal(max=n)
        last = Signal()
        self.comb += [
            last.eq(mux == (n-1)),
            source.stb.eq(sink.stb),
            sink.ack.eq(last & source.ack)
        ]
        self.sync += [
            If(source.stb & source.ack,
                If(last,
                    mux.eq(0)
                ).Else(
                    mux.eq(mux + 1)
                )
            )
        ]
        cases = {}
        for i in range(n):
            chunk = n-i-1 if reverse else i
            cases[i] = [source.payload.raw_bits().eq(getattr(sink.payload, "chunk"+str(chunk)).raw_bits())]
        self.comb += Case(mux, cases).makedefault()

        for f in description_from.param_layout:
            src = getattr(self.sink, f[0])
            dst = getattr(self.source, f[0])
            self.comb += dst.eq(src)

        self.comb += source.eop.eq(sink.eop & last)


class Pack(Module):
    def __init__(self, layout_from, n, reverse=False):
        self.sink = sink = Endpoint(layout_from)
        description_to = copy(sink.description)
        description_to.payload_layout = pack_layout(description_to.payload_layout, n)
        self.source = source = Endpoint(description_to)

        # # #

        demux = Signal(max=n)

        load_part = Signal()
        strobe_all = Signal()
        cases = {}
        for i in range(n):
            chunk = n-i-1 if reverse else i
            cases[i] = [getattr(source.payload, "chunk"+str(chunk)).raw_bits().eq(sink.payload.raw_bits())]
        self.comb += [
            sink.ack.eq(~strobe_all | source.ack),
            source.stb.eq(strobe_all),
            load_part.eq(sink.stb & sink.ack)
        ]

        for f in description_to.param_layout:
            src = getattr(self.sink, f[0])
            dst = getattr(self.source, f[0])
            self.sync += If(load_part, dst.eq(src))

        demux_last = ((demux == (n - 1)) | sink.eop)

        self.sync += [
            If(source.ack, strobe_all.eq(0)),
            If(load_part,
                Case(demux, cases),
                If(demux_last,
                    demux.eq(0),
                    strobe_all.eq(1)
                ).Else(
                    demux.eq(demux + 1)
                )
            ),
            If(source.stb & source.ack,
                source.eop.eq(sink.eop),
            ).Elif(sink.stb & sink.ack,
                source.eop.eq(sink.eop | source.eop)
            )
        ]


class Pipeline(Module):
    def __init__(self, *modules):
        n = len(modules)
        m = modules[0]
        # expose sink of first module
        # if available
        if hasattr(m, "sink"):
            self.sink = m.sink
        for i in range(1, n):
            m_n = modules[i]
            if isinstance(m, Endpoint):
                source = m
            else:
                source = m.source
            if isinstance(m_n, Endpoint):
                sink = m_n
            else:
                sink = m_n.sink
            if m is not m_n:
                self.comb += source.connect(sink)
            m = m_n
        # expose source of last module
        # if available
        if hasattr(m, "source"):
            self.source = m.source


# Add buffers on Endpoints (can be used to improve timings)
class BufferizeEndpoints(ModuleTransformer):
    def __init__(self, endpoint_dict):
        self.endpoint_dict = endpoint_dict

    def transform_instance(self, submodule):
        for name, direction in self.endpoint_dict.items():
            endpoint = getattr(submodule, name)
            # add buffer on sinks
            if direction == DIR_SINK:
                buf = Buffer(endpoint.description)
                submodule.submodules += buf
                setattr(submodule, name, buf.sink)
                submodule.comb += buf.source.connect(endpoint)
            # add buffer on sources
            elif direction == DIR_SOURCE:
                buf = Buffer(endpoint.description)
                submodule.submodules += buf
                submodule.comb += endpoint.connect(buf.sink)
                setattr(submodule, name, buf.source)
            else:
                raise ValueError


# XXX
