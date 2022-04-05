#
# This file is part of LiteX.
#
# Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2018 Tim 'mithro' Ansell <me@mith.ro>
# SPDX-License-Identifier: BSD-2-Clause

import math

from migen import *
from migen.util.misc import xdir
from migen.genlib import fifo
from migen.genlib.cdc import MultiReg, PulseSynchronizer, AsyncResetSynchronizer

from litex.soc.interconnect.csr import *

# Endpoint -----------------------------------------------------------------------------------------

(DIR_SINK, DIR_SOURCE) = range(2)

def _make_m2s(layout):
    r = []
    for f in layout:
        if isinstance(f[1], (int, tuple)):
            r.append((f[0], f[1], DIR_M_TO_S))
        else:
            r.append((f[0], _make_m2s(f[1])))
    return r

def set_reset_less(field):
    if isinstance(field, Signal):
        field.reset_less = True
    elif isinstance(field, Record):
        for s, _ in field.iter_flat():
            s.reset_less = True

class EndpointDescription:
    def __init__(self, payload_layout=[], param_layout=[]):
        self.payload_layout = payload_layout
        self.param_layout   = param_layout

    def get_full_layout(self):
        reserved   = {"valid", "ready", "payload", "param", "first", "last", "description"}
        attributed = set()
        for f in self.payload_layout + self.param_layout:
            if f[0] in attributed:
                raise ValueError(f[0] + " already attributed in payload or param layout")
            if f[0] in reserved:
                raise ValueError(f[0] + " cannot be used in endpoint layout")
            attributed.add(f[0])

        full_layout = [
            ("valid",   1, DIR_M_TO_S),
            ("ready",   1, DIR_S_TO_M),
            ("first",   1, DIR_M_TO_S),
            ("last",    1, DIR_M_TO_S),
            ("payload", _make_m2s(self.payload_layout)),
            ("param",   _make_m2s(self.param_layout))
        ]
        return full_layout


class Endpoint(Record):
    def __init__(self, description_or_layout=[], name=None, **kwargs):
        if isinstance(description_or_layout, EndpointDescription):
            self.description = description_or_layout
        else:
            self.description = EndpointDescription(description_or_layout)
        Record.__init__(self, self.description.get_full_layout(), name, **kwargs)
        set_reset_less(self.first)
        set_reset_less(self.last)
        #set_reset_less(self.payload) # FIXME: cause issues with LiteSATA, understand why and uncomment.
        set_reset_less(self.param)

    def __getattr__(self, name):
        try:
            return getattr(object.__getattribute__(self, "payload"), name)
        except:
            return getattr(object.__getattribute__(self, "param"), name)

# Actor --------------------------------------------------------------------------------------------

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
            source.valid.eq(sink.valid),
            source.first.eq(sink.first),
            source.last.eq(sink.last),
            sink.ready.eq(source.ready),
        ]


class PipelinedActor(BinaryActor):
    def __init__(self, latency):
        self.latency = latency
        self.pipe_ce = Signal()
        self.busy    = Signal()
        BinaryActor.__init__(self, latency)

    def build_binary_control(self, sink, source, latency):
        busy  = 0
        valid = sink.valid
        for i in range(latency):
            valid_n = Signal()
            self.sync += If(self.pipe_ce, valid_n.eq(valid))
            valid = valid_n
            busy = busy | valid

        self.comb += [
            self.pipe_ce.eq(source.ready | ~valid),
            sink.ready.eq(self.pipe_ce),
            source.valid.eq(valid),
            self.busy.eq(busy)
        ]
        first = sink.valid & sink.first
        last  = sink.valid & sink.last
        for i in range(latency):
            first_n = Signal(reset_less=True)
            last_n  = Signal(reset_less=True)
            self.sync += \
                If(self.pipe_ce,
                    first_n.eq(first),
                    last_n.eq(last)
                )
            first = first_n
            last  = last_n
        self.comb += [
            source.first.eq(first),
            source.last.eq(last)
        ]

# FIFO ---------------------------------------------------------------------------------------------

class _FIFOWrapper(Module):
    def __init__(self, fifo_class, layout, depth):
        self.sink   = sink   = Endpoint(layout)
        self.source = source = Endpoint(layout)

        # # #

        description = sink.description
        fifo_layout = [
            ("payload", description.payload_layout),
            ("param",   description.param_layout),
            ("first",   1),
            ("last",    1)
        ]

        self.submodules.fifo = fifo = fifo_class(layout_len(fifo_layout), depth)
        fifo_in  = Record(fifo_layout)
        fifo_out = Record(fifo_layout)
        self.comb += [
            fifo.din.eq(fifo_in.raw_bits()),
            fifo_out.raw_bits().eq(fifo.dout)
        ]

        self.comb += [
            sink.ready.eq(fifo.writable),
            fifo.we.eq(sink.valid),
            fifo_in.first.eq(sink.first),
            fifo_in.last.eq(sink.last),
            fifo_in.payload.eq(sink.payload),
            fifo_in.param.eq(sink.param),

            source.valid.eq(fifo.readable),
            source.first.eq(fifo_out.first),
            source.last.eq(fifo_out.last),
            source.payload.eq(fifo_out.payload),
            source.param.eq(fifo_out.param),
            fifo.re.eq(source.ready)
        ]


class SyncFIFO(_FIFOWrapper):
    def __init__(self, layout, depth, buffered=False):
        assert depth >= 0
        if depth >= 2:
            _FIFOWrapper.__init__(self,
                fifo_class = fifo.SyncFIFOBuffered if buffered else fifo.SyncFIFO,
                layout     = layout,
                depth      = depth)
            self.depth = self.fifo.depth
            self.level = self.fifo.level
        elif depth == 1:
            buf = Buffer(layout)
            self.submodules += buf
            self.sink   = buf.sink
            self.source = buf.source
            self.depth  = 1
            self.level  = Signal()
        elif depth == 0:
            self.sink   = Endpoint(layout)
            self.source = Endpoint(layout)
            self.comb += self.sink.connect(self.source)
            self.depth = 0
            self.level = Signal()


class AsyncFIFO(_FIFOWrapper):
    def __init__(self, layout, depth=None, buffered=False):
        depth = 4 if depth is None else depth
        assert depth >= 4
        _FIFOWrapper.__init__(self,
            fifo_class = fifo.AsyncFIFOBuffered if buffered else fifo.AsyncFIFO,
            layout     = layout,
            depth      = depth)

# ClockDomainCrossing ------------------------------------------------------------------------------

class ClockDomainCrossing(Module):
    def __init__(self, layout, cd_from="sys", cd_to="sys", depth=None, with_common_rst=False):
        self.sink   = Endpoint(layout)
        self.source = Endpoint(layout)

        # # #

        # Same Clk Domains.
        if cd_from == cd_to:
            # No adaptation.
            self.comb += self.sink.connect(self.source)
        # Different Clk Domains.
        else:
            if with_common_rst:
                # Create intermediate Clk Domains and generate a common Rst.
                _cd_id   = id(self) # FIXME: Improve, used to allow build with anonymous modules.
                _cd_rst  = Signal()
                _cd_from = ClockDomain(f"from{_cd_id}")
                _cd_to   = ClockDomain(f"to{_cd_id}")
                self.clock_domains += _cd_from, _cd_to
                self.comb += [
                    _cd_from.clk.eq(ClockSignal(cd_from)),
                    _cd_to.clk.eq(  ClockSignal(cd_to)),
                    _cd_rst.eq(ResetSignal(cd_from) | ResetSignal(cd_to))
                ]
                cd_from = _cd_from.name
                cd_to   = _cd_to.name
                # Use common Rst on both Clk Domains (through AsyncResetSynchronizer).
                self.specials += [
                   AsyncResetSynchronizer(_cd_from, _cd_rst),
                   AsyncResetSynchronizer(_cd_to,   _cd_rst),
                ]

            # Add Asynchronous FIFO
            cdc = AsyncFIFO(layout, depth)
            cdc = ClockDomainsRenamer({"write": cd_from, "read": cd_to})(cdc)
            self.submodules += cdc

            # Sink -> AsyncFIFO -> Source.
            self.comb += self.sink.connect(cdc.sink)
            self.comb += cdc.source.connect(self.source)

# Mux/Demux ----------------------------------------------------------------------------------------

class Multiplexer(Module):
    def __init__(self, layout, n):
        self.source = Endpoint(layout)
        sinks = []
        for i in range(n):
            sink = Endpoint(layout)
            setattr(self, "sink"+str(i), sink)
            sinks.append(sink)
        self.sel = Signal(max=max(n, 2))

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
        self.sel = Signal(max=max(n, 2))

        # # #

        cases = {}
        for i, source in enumerate(sources):
            cases[i] = self.sink.connect(source)
        self.comb += Case(self.sel, cases)


# Gate ---------------------------------------------------------------------------------------------

class Gate(Module):
    def __init__(self, layout, sink_ready_when_disabled=False):
        self.sink   = Endpoint(layout)
        self.source = Endpoint(layout)
        self.enable = Signal()

        # # #

        self.comb += [
            If(self.enable,
                self.sink.connect(self.source)
            ).Else(
                self.sink.ready.eq(int(sink_ready_when_disabled))
            )
        ]

# Converter ----------------------------------------------------------------------------------------

class _UpConverter(Module):
    def __init__(self, nbits_from, nbits_to, ratio, reverse):
        self.sink   = sink   = Endpoint([("data", nbits_from)])
        self.source = source = Endpoint([("data", nbits_to), ("valid_token_count", bits_for(ratio))])
        self.latency = 1

        # # #

        # Control path
        demux      = Signal(max=ratio)
        load_part  = Signal()
        strobe_all = Signal()
        self.comb += [
            sink.ready.eq(~strobe_all | source.ready),
            source.valid.eq(strobe_all),
            load_part.eq(sink.valid & sink.ready)
        ]

        demux_last = ((demux == (ratio - 1)) | sink.last)

        self.sync += [
            If(source.ready, strobe_all.eq(0)),
            If(load_part,
                If(demux_last,
                    demux.eq(0),
                    strobe_all.eq(1)
                ).Else(
                    demux.eq(demux + 1)
                )
            ),
            If(source.valid & source.ready,
                If(sink.valid & sink.ready,
                    source.first.eq(sink.first),
                    source.last.eq(sink.last)
                ).Else(
                    source.first.eq(0),
                    source.last.eq(0)
                )
            ).Elif(sink.valid & sink.ready,
                source.first.eq(sink.first | source.first),
                source.last.eq(sink.last | source.last)
            )
        ]

        # Data path
        cases = {}
        for i in range(ratio):
            n = ratio-i-1 if reverse else i
            cases[i] = source.data[n*nbits_from:(n+1)*nbits_from].eq(sink.data)
        self.sync += If(load_part, Case(demux, cases))

        # Valid token count
        self.sync += If(load_part, source.valid_token_count.eq(demux + 1))


class _DownConverter(Module):
    def __init__(self, nbits_from, nbits_to, ratio, reverse):
        self.sink   = sink   = Endpoint([("data", nbits_from)])
        self.source = source = Endpoint([("data", nbits_to), ("valid_token_count", 1)])
        self.latency = 0

        # # #

        # Control path
        mux   = Signal(max=ratio)
        first = Signal()
        last  = Signal()
        self.comb += [
            first.eq(mux == 0),
            last.eq(mux == (ratio-1)),
            source.valid.eq(sink.valid),
            source.first.eq(sink.first & first),
            source.last.eq(sink.last & last),
            sink.ready.eq(last & source.ready)
        ]
        self.sync += \
            If(source.valid & source.ready,
                If(last,
                    mux.eq(0)
                ).Else(
                    mux.eq(mux + 1)
                )
            )

        # Data path
        cases = {}
        for i in range(ratio):
            n = ratio-i-1 if reverse else i
            cases[i] = source.data.eq(sink.data[n*nbits_to:(n+1)*nbits_to])
        self.comb += Case(mux, cases).makedefault()

        # Valid token count
        self.comb += source.valid_token_count.eq(last)


class _IdentityConverter(Module):
    def __init__(self, nbits_from, nbits_to, ratio, reverse):
        self.sink   = sink   = Endpoint([("data", nbits_from)])
        self.source = source = Endpoint([("data", nbits_to), ("valid_token_count", 1)])
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
    def __init__(self, nbits_from, nbits_to,
        reverse                  = False,
        report_valid_token_count = False):
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
            self.comb += converter.source.connect(self.source, omit=set(["valid_token_count"]))


class StrideConverter(Module):
    def __init__(self, description_from, description_to, reverse=False):
        self.sink   = sink   = Endpoint(description_from)
        self.source = source = Endpoint(description_to)

        # # #

        nbits_from = len(sink.payload.raw_bits())
        nbits_to   = len(source.payload.raw_bits())

        converter = Converter(nbits_from, nbits_to, reverse)
        self.submodules += converter

        # Cast sink to converter.sink (user fields --> raw bits)
        self.comb += [
            converter.sink.valid.eq(sink.valid),
            converter.sink.first.eq(sink.first),
            converter.sink.last.eq(sink.last),
            sink.ready.eq(converter.sink.ready)
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


        # Cast converter.source to source (raw bits --> user fields)
        self.comb += [
            source.valid.eq(converter.source.valid),
            source.first.eq(converter.source.first),
            source.last.eq(converter.source.last),
            converter.source.ready.eq(source.ready)
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

        # Connect params
        if converter.latency == 0:
            self.comb += source.param.eq(sink.param)
        elif converter.latency == 1:
            self.sync += source.param.eq(sink.param)
        else:
            raise ValueError

# Gearbox ------------------------------------------------------------------------------------------

def lcm(a, b):
    return (a*b)//math.gcd(a, b)


def inc_mod(s, m):
    return [s.eq(s + 1), If(s == (m -1), s.eq(0))]


class Gearbox(Module):
    def __init__(self, i_dw, o_dw, msb_first=True):
        self.sink   = sink   = Endpoint([("data", i_dw)])
        self.source = source = Endpoint([("data", o_dw)])

        # # #

        io_lcm = lcm(i_dw, o_dw)
        if (io_lcm//i_dw) < 2:
            io_lcm = io_lcm * 2
        if (io_lcm//o_dw) < 2:
            io_lcm = io_lcm * 2

        # Control path

        level   = Signal(max=io_lcm)
        i_inc   = Signal()
        i_count = Signal(max=io_lcm//i_dw)
        o_inc   = Signal()
        o_count = Signal(max=io_lcm//o_dw)

        self.comb += [
            sink.ready.eq(level < (io_lcm - i_dw)),
            source.valid.eq(level >= o_dw),
        ]
        self.comb += [
            i_inc.eq(sink.valid & sink.ready),
            o_inc.eq(source.valid & source.ready)
        ]
        self.sync += [
            If(i_inc, *inc_mod(i_count, io_lcm//i_dw)),
            If(o_inc, *inc_mod(o_count, io_lcm//o_dw)),
            If(i_inc & ~o_inc, level.eq(level + i_dw)),
            If(~i_inc & o_inc, level.eq(level - o_dw)),
            If(i_inc & o_inc, level.eq(level + i_dw - o_dw)),
        ]

        # Data path

        shift_register = Signal(io_lcm, reset_less=True)

        i_cases = {}
        i_data  = Signal(i_dw)
        if msb_first:
            self.comb += i_data.eq(sink.data)
        else:
            self.comb += i_data.eq(sink.data[::-1])
        for i in range(io_lcm//i_dw):
            i_cases[i] = shift_register[io_lcm - i_dw*(i+1):io_lcm - i_dw*i].eq(i_data)
        self.sync += If(sink.valid & sink.ready, Case(i_count, i_cases))

        o_cases = {}
        o_data  = Signal(o_dw)
        for i in range(io_lcm//o_dw):
            o_cases[i] = o_data.eq(shift_register[io_lcm - o_dw*(i+1):io_lcm - o_dw*i])
        self.comb += Case(o_count, o_cases)
        if msb_first:
            self.comb += source.data.eq(o_data)
        else:
            self.comb += source.data.eq(o_data[::-1])

# Shifter ------------------------------------------------------------------------------------------

class Shifter(PipelinedActor):
    def __init__(self, dw, shift=None):
        self.shift  = Signal(max=dw) if shift is None else shift
        self.sink   = sink   = Endpoint([("data", dw)])
        self.source = source = Endpoint([("data", dw)])
        PipelinedActor.__init__(self, latency=2)

        # # #

        # Accumulate current/last sink.data.
        r = Signal(2*dw)
        self.sync += If(self.pipe_ce,
            r[:dw].eq(r[dw:]),
            r[dw:].eq(sink.data)
        )

        # Select output data based on shift.
        cases = {}
        for i in range(dw):
            cases[i] = self.source.data.eq(r[i:dw+i])
        self.comb += Case(self.shift, cases)

# Monitor ------------------------------------------------------------------------------------------

class Monitor(Module, AutoCSR):
    def __init__(self, endpoint, count_width=32, clock_domain="sys",
        with_tokens     = False,
        with_overflows  = False,
        with_underflows = False):

        self.reset = CSR()
        self.latch = CSR()
        if with_tokens:
            self.tokens = CSRStatus(count_width)
        if with_overflows:
            self.overflows = CSRStatus(count_width)
        if with_underflows:
            self.underflows = CSRStatus(count_width)

        # # #

        reset = Signal()
        latch = Signal()
        if clock_domain == "sys":
            self.comb += reset.eq(self.reset.re)
            self.comb += latch.eq(self.latch.re)
        else:
            reset_ps = PulseSynchronizer("sys", clock_domain)
            latch_ps = PulseSynchronizer("sys", clock_domain)
            self.submodules += reset_ps, latch_ps
            self.comb += reset_ps.i.eq(self.reset.re)
            self.comb += reset.eq(reset_ps.o)
            self.comb += latch_ps.i.eq(self.latch.re)
            self.comb += latch.eq(latch_ps.o)

        # Generic Monitor Counter ------------------------------------------------------------------
        class MonitorCounter(Module):
            def __init__(self, reset, latch, enable, count):
                _count         = Signal.like(count)
                _count_latched = Signal.like(count)
                _sync = getattr(self.sync, clock_domain)
                _sync += [
                    If(reset,
                        _count.eq(0),
                        _count_latched.eq(0),
                    ).Elif(enable,
                        If(_count != (2**len(count)-1),
                            _count.eq(_count + 1)
                        )
                    ),
                    If(latch,
                        _count_latched.eq(_count)
                    )
                ]
                self.specials += MultiReg(_count_latched, count)

        # Tokens Count -----------------------------------------------------------------------------
        if with_tokens:
            token_counter = MonitorCounter(reset, latch, endpoint.valid & endpoint.ready, self.tokens.status)
            self.submodules += token_counter

        # Overflows Count (only useful when endpoint is expected to always be ready) ---------------
        if with_overflows:
            overflow_counter = MonitorCounter(reset, latch, endpoint.valid & ~endpoint.ready, self.overflows.status)
            self.submodules += overflow_counter

        # Underflows Count (only useful when endpoint is expected to always be valid) --------------
        if with_underflows:
            underflow_counter = MonitorCounter(reset, latch, ~endpoint.valid & endpoint.ready, self.underflows.status)
            self.submodules += underflow_counter

# Pipe ---------------------------------------------------------------------------------------------

class PipeValid(Module):
    """Pipe valid/payload to cut timing path"""
    def __init__(self, layout):
        self.sink   = sink   = Endpoint(layout)
        self.source = source = Endpoint(layout)

        # # #

        # Pipe when source is not valid or is ready.
        self.sync += [
            If(~source.valid | source.ready,
                source.valid.eq(sink.valid),
                source.first.eq(sink.first),
                source.last.eq(sink.last),
                source.payload.eq(sink.payload),
                source.param.eq(sink.param),
            )
        ]
        self.comb += sink.ready.eq(~source.valid | source.ready)


class PipeReady(Module):
    """Pipe ready to cut timing path"""
    def __init__(self, layout):
        self.sink   = sink   = Endpoint(layout)
        self.source = source = Endpoint(layout)

        # # #

        valid  = Signal()
        sink_d = Endpoint(layout)

        self.sync += [
            If(sink.valid & ~source.ready,
                valid.eq(1)
            ).Elif(source.ready,
                valid.eq(0)
            ),
            If(~source.ready & ~valid,
                sink_d.eq(sink)
            )
        ]
        self.comb += [
            sink.ready.eq(~valid),
            If(valid,
                sink_d.connect(source, omit={"ready"})
            ).Else(
                sink.connect(source, omit={"ready"})
            )
        ]

# Buffer -------------------------------------------------------------------------------------------

class Buffer(PipeValid): pass # FIXME: Replace Buffer with PipeValid in codebase?

# Cast ---------------------------------------------------------------------------------------------

class Cast(CombinatorialActor):
    def __init__(self, layout_from, layout_to, reverse_from=False, reverse_to=False):
        self.sink   = Endpoint(_rawbits_layout(layout_from))
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

# Unpack/Pack --------------------------------------------------------------------------------------

class Unpack(Module):
    def __init__(self, n, layout_to, reverse=False):
        self.source = source = Endpoint(layout_to)
        description_from = Endpoint(layout_to).description
        description_from.payload_layout = pack_layout(description_from.payload_layout, n)
        self.sink = sink = Endpoint(description_from)

        # # #

        mux   = Signal(max=n)
        first = Signal()
        last  = Signal()
        self.comb += [
            first.eq(mux == 0),
            last.eq(mux == (n-1)),
            source.valid.eq(sink.valid),
            sink.ready.eq(last & source.ready)
        ]
        self.sync += [
            If(source.valid & source.ready,
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

        self.comb += [
            source.first.eq(sink.first & first),
            source.last.eq(sink.last & last)
        ]


class Pack(Module):
    def __init__(self, layout_from, n, reverse=False):
        self.sink = sink = Endpoint(layout_from)
        description_to = Endpoint(layout_from).description
        description_to.payload_layout = pack_layout(description_to.payload_layout, n)
        self.source = source = Endpoint(description_to)

        # # #

        demux = Signal(max=n)

        load_part  = Signal()
        strobe_all = Signal()
        cases = {}
        for i in range(n):
            chunk = n-i-1 if reverse else i
            cases[i] = [getattr(source.payload, "chunk"+str(chunk)).raw_bits().eq(sink.payload.raw_bits())]
        self.comb += [
            sink.ready.eq(~strobe_all | source.ready),
            source.valid.eq(strobe_all),
            load_part.eq(sink.valid & sink.ready)
        ]

        for f in description_to.param_layout:
            src = getattr(self.sink, f[0])
            dst = getattr(self.source, f[0])
            self.sync += If(load_part, dst.eq(src))

        demux_last = ((demux == (n - 1)) | sink.last)

        self.sync += [
            If(source.ready, strobe_all.eq(0)),
            If(load_part,
                Case(demux, cases),
                If(demux_last,
                    demux.eq(0),
                    strobe_all.eq(1)
                ).Else(
                    demux.eq(demux + 1)
                )
            ),
            If(source.valid & source.ready,
                source.first.eq(sink.first),
                source.last.eq(sink.last),
            ).Elif(sink.valid & sink.ready,
                source.first.eq(sink.first | source.first),
                source.last.eq(sink.last | source.last)
            )
        ]

# Pipeline -----------------------------------------------------------------------------------------

class Pipeline(Module):
    def __init__(self, *modules):
        n = len(modules)
        m = modules[0]
        # Expose sink of first module if available.
        if hasattr(m, "sink"):
            self.sink = m.sink
        # Iterate on Modules/Endpoints.
        for i in range(1, n):
            m_n = modules[i]
            # If m is an Endpoint, use it as Source, else use Module.source.
            source = m if isinstance(m, Endpoint) else m.source
            # If m_n is an Endpoint, use it as Sink, else use Module.sink.
            sink = m_n if isinstance(m_n, Endpoint) else m_n.sink
            # Connect Source to Sink (when m is not m_n).
            if m is not m_n:
                self.comb += source.connect(sink)
            # Update m.
            m = m_n
        # Expose source of last module if available.
        if hasattr(m, "source"):
            self.source = m.source

# BufferizeEndpoints -------------------------------------------------------------------------------

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
