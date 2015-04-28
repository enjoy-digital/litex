from misoclib.com.liteeth.common import *


class LiteEthEtherboneRecordPacketizer(Packetizer):
    def __init__(self):
        Packetizer.__init__(self,
            eth_etherbone_record_description(32),
            eth_etherbone_packet_user_description(32),
            etherbone_record_header)


class LiteEthEtherboneRecordDepacketizer(Depacketizer):
    def __init__(self):
        Depacketizer.__init__(self,
            eth_etherbone_packet_user_description(32),
            eth_etherbone_record_description(32),
            etherbone_record_header)


class LiteEthEtherboneRecordReceiver(Module):
    def __init__(self, buffer_depth=256):
        self.sink = sink = Sink(eth_etherbone_record_description(32))
        self.source = source = Source(eth_etherbone_mmap_description(32))

        # # #

        fifo = SyncFIFO(eth_etherbone_record_description(32), buffer_depth,
                        buffered=True)
        self.submodules += fifo
        self.comb += Record.connect(sink, fifo.sink)

        self.submodules.base_addr = base_addr = FlipFlop(32)
        self.comb += base_addr.d.eq(fifo.source.data)

        self.submodules.counter = counter = Counter(max=512)

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            fifo.source.ack.eq(1),
            counter.reset.eq(1),
            If(fifo.source.stb & fifo.source.sop,
                base_addr.ce.eq(1),
                If(fifo.source.wcount,
                    NextState("RECEIVE_WRITES")
                ).Elif(fifo.source.rcount,
                    NextState("RECEIVE_READS")
                )
            )
        )
        fsm.act("RECEIVE_WRITES",
            source.stb.eq(fifo.source.stb),
            source.sop.eq(counter.value == 0),
            source.eop.eq(counter.value == fifo.source.wcount-1),
            source.count.eq(fifo.source.wcount),
            source.be.eq(fifo.source.byte_enable),
            source.addr.eq(base_addr.q[2:] + counter.value),
            source.we.eq(1),
            source.data.eq(fifo.source.data),
            fifo.source.ack.eq(source.ack),
            If(source.stb & source.ack,
                counter.ce.eq(1),
                If(source.eop,
                    If(fifo.source.rcount,
                        NextState("RECEIVE_BASE_RET_ADDR")
                    ).Else(
                        NextState("IDLE")
                    )
                )
            )
        )
        fsm.act("RECEIVE_BASE_RET_ADDR",
            counter.reset.eq(1),
            If(fifo.source.stb & fifo.source.sop,
                base_addr.ce.eq(1),
                NextState("RECEIVE_READS")
            )
        )
        fsm.act("RECEIVE_READS",
            source.stb.eq(fifo.source.stb),
            source.sop.eq(counter.value == 0),
            source.eop.eq(counter.value == fifo.source.rcount-1),
            source.count.eq(fifo.source.rcount),
            source.base_addr.eq(base_addr.q),
            source.addr.eq(fifo.source.data[2:]),
            fifo.source.ack.eq(source.ack),
            If(source.stb & source.ack,
                counter.ce.eq(1),
                If(source.eop,
                    NextState("IDLE")
                )
            )
        )


class LiteEthEtherboneRecordSender(Module):
    def __init__(self, buffer_depth=256):
        self.sink = sink = Sink(eth_etherbone_mmap_description(32))
        self.source = source = Source(eth_etherbone_record_description(32))

        # # #

        pbuffer = Buffer(eth_etherbone_mmap_description(32), buffer_depth)
        self.submodules += pbuffer
        self.comb += Record.connect(sink, pbuffer.sink)

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            pbuffer.source.ack.eq(1),
            If(pbuffer.source.stb & pbuffer.source.sop,
                pbuffer.source.ack.eq(0),
                NextState("SEND_BASE_ADDRESS")
            )
        )
        self.comb += [
            source.byte_enable.eq(pbuffer.source.be),
            If(pbuffer.source.we,
                source.wcount.eq(pbuffer.source.count)
            ).Else(
                source.rcount.eq(pbuffer.source.count)
            )
        ]

        fsm.act("SEND_BASE_ADDRESS",
            source.stb.eq(pbuffer.source.stb),
            source.sop.eq(1),
            source.eop.eq(0),
            source.data.eq(pbuffer.source.base_addr),
            If(source.ack,
                NextState("SEND_DATA")
            )
        )
        fsm.act("SEND_DATA",
            source.stb.eq(pbuffer.source.stb),
            source.sop.eq(0),
            source.eop.eq(pbuffer.source.eop),
            source.data.eq(pbuffer.source.data),
            If(source.stb & source.ack,
                pbuffer.source.ack.eq(1),
                If(source.eop,
                    NextState("IDLE")
                )
            )
        )


# Limitation: For simplicity we only support 1 record per packet
class LiteEthEtherboneRecord(Module):
    def __init__(self, endianness="big"):
        self.sink = sink = Sink(eth_etherbone_packet_user_description(32))
        self.source = source = Sink(eth_etherbone_packet_user_description(32))

        # # #

        # receive record, decode it and generate mmap stream
        self.submodules.depacketizer = depacketizer = LiteEthEtherboneRecordDepacketizer()
        self.submodules.receiver = receiver = LiteEthEtherboneRecordReceiver()
        self.comb += [
            Record.connect(sink, depacketizer.sink),
            Record.connect(depacketizer.source, receiver.sink)
        ]
        if endianness is "big":
            self.comb += receiver.sink.data.eq(reverse_bytes(depacketizer.source.data))

        # save last ip address
        last_ip_address = Signal(32)
        self.sync += [
            If(sink.stb & sink.sop & sink.ack,
                last_ip_address.eq(sink.ip_address)
            )
        ]

        # receive mmap stream, encode it and send records
        self.submodules.sender = sender = LiteEthEtherboneRecordSender()
        self.submodules.packetizer = packetizer = LiteEthEtherboneRecordPacketizer()
        self.comb += [
            Record.connect(sender.source, packetizer.sink),
            Record.connect(packetizer.source, source),
            # XXX improve this
            source.length.eq(sender.source.wcount*4 + 4 + etherbone_record_header.length),
            source.ip_address.eq(last_ip_address)
        ]
        if endianness is "big":
            self.comb += packetizer.sink.data.eq(reverse_bytes(sender.source.data))
