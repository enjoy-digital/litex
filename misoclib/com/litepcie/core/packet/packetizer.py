from migen.fhdl.std import *
from migen.actorlib.structuring import *
from migen.genlib.fsm import FSM, NextState
from migen.genlib.misc import chooser

from misoclib.com.litepcie.core.packet.common import *
from misoclib.com.litepcie.core.switch.arbiter import Arbiter


def _encode_header(h_dict, h_signal, obj):
    r = []
    for k, v in sorted(h_dict.items()):
        start = v.word*32+v.offset
        end = start+v.width
        r.append(h_signal[start:end].eq(getattr(obj, k)))
    return r


class HeaderInserter(Module):
    def __init__(self, dw):
        self.sink = sink = Sink(tlp_raw_layout(dw))
        self.source = source = Source(phy_layout(dw))

        ###

        fsm = FSM(reset_state="HEADER1")
        self.submodules += fsm

        sink_dat_r = Signal(dw)
        sink_eop_r = Signal()
        self.sync += \
            If(sink.stb & sink.ack,
                sink_dat_r.eq(sink.dat),
                sink_eop_r.eq(sink.eop)
            )

        fsm.act("HEADER1",
            sink.ack.eq(1),
            If(sink.stb & sink.sop,
                sink.ack.eq(0),
                source.stb.eq(1),
                source.sop.eq(1),
                source.eop.eq(0),
                source.dat.eq(sink.header[:64]),
                source.be.eq(0xff),
                If(source.stb & source.ack,
                    NextState("HEADER2"),
                )
            )
        )
        fsm.act("HEADER2",
            source.stb.eq(1),
            source.sop.eq(0),
            source.eop.eq(sink.eop),
            source.dat.eq(Cat(sink.header[64:96], reverse_bytes(sink.dat[:32]))),
            source.be.eq(Cat(Signal(4, reset=0xf), reverse_bits(sink.be[:4]))),
            If(source.stb & source.ack,
                sink.ack.eq(1),
                If(source.eop,
                    NextState("HEADER1")
                ).Else(
                    NextState("COPY")
                )
            )
        )
        fsm.act("COPY",
            source.stb.eq(sink.stb | sink_eop_r),
            source.sop.eq(0),
            source.eop.eq(sink_eop_r),
            source.dat.eq(Cat(reverse_bytes(sink_dat_r[32:64]), reverse_bytes(sink.dat[:32]))),
            If(sink_eop_r,
                source.be.eq(0x0f)
            ).Else(
                source.be.eq(0xff)
            ),
            If(source.stb & source.ack,
                sink.ack.eq(~sink_eop_r),
                If(source.eop,
                    NextState("HEADER1")
                )
            )
        )


class Packetizer(Module):
    def __init__(self, dw):
        self.req_sink = req_sink = Sink(request_layout(dw))
        self.cmp_sink = cmp_sink = Sink(completion_layout(dw))

        self.source = Source(phy_layout(dw))

        ###

        # format TLP request and encode it
        tlp_req = Sink(tlp_request_layout(dw))
        self.comb += [
            tlp_req.stb.eq(req_sink.stb),
            req_sink.ack.eq(tlp_req.ack),
            tlp_req.sop.eq(req_sink.sop),
            tlp_req.eop.eq(req_sink.eop),

            If(req_sink.we,
                Cat(tlp_req.type, tlp_req.fmt).eq(fmt_type_dict["mem_wr32"])
            ).Else(
                Cat(tlp_req.type, tlp_req.fmt).eq(fmt_type_dict["mem_rd32"])
            ),

            tlp_req.tc.eq(0),
            tlp_req.td.eq(0),
            tlp_req.ep.eq(0),
            tlp_req.attr.eq(0),
            tlp_req.length.eq(req_sink.len),

            tlp_req.requester_id.eq(req_sink.req_id),
            tlp_req.tag.eq(req_sink.tag),
            If(req_sink.len > 1,
                tlp_req.last_be.eq(0xf)
            ).Else(
                tlp_req.last_be.eq(0x0)
            ),
            tlp_req.first_be.eq(0xf),
            tlp_req.address.eq(req_sink.adr[2:]),

            tlp_req.dat.eq(req_sink.dat),
            If(req_sink.we,
                tlp_req.be.eq(0xff)
            ).Else(
                tlp_req.be.eq(0x00)
            ),
        ]

        tlp_raw_req = Sink(tlp_raw_layout(dw))
        self.comb += [
            tlp_raw_req.stb.eq(tlp_req.stb),
            tlp_req.ack.eq(tlp_raw_req.ack),
            tlp_raw_req.sop.eq(tlp_req.sop),
            tlp_raw_req.eop.eq(tlp_req.eop),
            _encode_header(tlp_request_header, tlp_raw_req.header, tlp_req),
            tlp_raw_req.dat.eq(tlp_req.dat),
            tlp_raw_req.be.eq(tlp_req.be),
        ]

        # format TLP completion and encode it
        tlp_cmp = Sink(tlp_completion_layout(dw))
        self.comb += [
            tlp_cmp.stb.eq(cmp_sink.stb),
            cmp_sink.ack.eq(tlp_cmp.ack),
            tlp_cmp.sop.eq(cmp_sink.sop),
            tlp_cmp.eop.eq(cmp_sink.eop),

            tlp_cmp.tc.eq(0),
            tlp_cmp.td.eq(0),
            tlp_cmp.ep.eq(0),
            tlp_cmp.attr.eq(0),
            tlp_cmp.length.eq(cmp_sink.len),

            tlp_cmp.completer_id.eq(cmp_sink.cmp_id),
            If(cmp_sink.err,
                Cat(tlp_cmp.type, tlp_cmp.fmt).eq(fmt_type_dict["cpl"]),
                tlp_cmp.status.eq(cpl_dict["ur"])
            ).Else(
                Cat(tlp_cmp.type, tlp_cmp.fmt).eq(fmt_type_dict["cpld"]),
                tlp_cmp.status.eq(cpl_dict["sc"])
            ),
            tlp_cmp.bcm.eq(0),
            tlp_cmp.byte_count.eq(cmp_sink.len*4),

            tlp_cmp.requester_id.eq(cmp_sink.req_id),
            tlp_cmp.tag.eq(cmp_sink.tag),
            tlp_cmp.lower_address.eq(cmp_sink.adr),

            tlp_cmp.dat.eq(cmp_sink.dat),
            tlp_cmp.be.eq(0xff)
        ]

        tlp_raw_cmp = Sink(tlp_raw_layout(dw))
        self.comb += [
            tlp_raw_cmp.stb.eq(tlp_cmp.stb),
            tlp_cmp.ack.eq(tlp_raw_cmp.ack),
            tlp_raw_cmp.sop.eq(tlp_cmp.sop),
            tlp_raw_cmp.eop.eq(tlp_cmp.eop),
            _encode_header(tlp_completion_header, tlp_raw_cmp.header, tlp_cmp),
            tlp_raw_cmp.dat.eq(tlp_cmp.dat),
            tlp_raw_cmp.be.eq(tlp_cmp.be),
        ]

        # arbitrate
        tlp_raw = Sink(tlp_raw_layout(dw))
        self.submodules.arbitrer = Arbiter([tlp_raw_req, tlp_raw_cmp], tlp_raw)

        # insert header
        header_inserter = HeaderInserter(dw)
        self.submodules += header_inserter
        self.comb += [
            Record.connect(tlp_raw, header_inserter.sink),
            Record.connect(header_inserter.source, self.source)
        ]
