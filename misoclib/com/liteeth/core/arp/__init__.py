from misoclib.com.liteeth.common import *

_arp_table_layout = [
        ("reply", 1),
        ("request", 1),
        ("ip_address", 32),
        ("mac_address", 48)
    ]


class LiteEthARPPacketizer(Packetizer):
    def __init__(self):
        Packetizer.__init__(self,
            eth_arp_description(8),
            eth_mac_description(8),
            arp_header)


class LiteEthARPTX(Module):
    def __init__(self, mac_address, ip_address):
        self.sink = sink = Sink(_arp_table_layout)
        self.source = source = Source(eth_mac_description(8))

        # # #

        self.submodules.packetizer = packetizer = LiteEthARPPacketizer()

        counter = Counter(max=max(arp_header.length, eth_min_len))
        self.submodules += counter

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            sink.ack.eq(1),
            counter.reset.eq(1),
            If(sink.stb,
                sink.ack.eq(0),
                NextState("SEND")
            )
        )
        self.comb += [
            packetizer.sink.sop.eq(counter.value == 0),
            packetizer.sink.eop.eq(counter.value == max(arp_header.length, eth_min_len)-1),
            packetizer.sink.hwtype.eq(arp_hwtype_ethernet),
            packetizer.sink.proto.eq(arp_proto_ip),
            packetizer.sink.hwsize.eq(6),
            packetizer.sink.protosize.eq(4),
            packetizer.sink.sender_mac.eq(mac_address),
            packetizer.sink.sender_ip.eq(ip_address),
            If(sink.reply,
                packetizer.sink.opcode.eq(arp_opcode_reply),
                packetizer.sink.target_mac.eq(sink.mac_address),
                packetizer.sink.target_ip.eq(sink.ip_address)
            ).Elif(sink.request,

                packetizer.sink.opcode.eq(arp_opcode_request),
                packetizer.sink.target_mac.eq(0xffffffffffff),
                packetizer.sink.target_ip.eq(sink.ip_address)
            )
        ]
        fsm.act("SEND",
            packetizer.sink.stb.eq(1),
            Record.connect(packetizer.source, source),
            source.target_mac.eq(packetizer.sink.target_mac),
            source.sender_mac.eq(mac_address),
            source.ethernet_type.eq(ethernet_type_arp),
            If(source.stb & source.ack,
                counter.ce.eq(1),
                If(source.eop,
                    sink.ack.eq(1),
                    NextState("IDLE")
                )
            )
        )


class LiteEthARPDepacketizer(Depacketizer):
    def __init__(self):
        Depacketizer.__init__(self,
            eth_mac_description(8),
            eth_arp_description(8),
            arp_header)


class LiteEthARPRX(Module):
    def __init__(self, mac_address, ip_address):
        self.sink = sink = Sink(eth_mac_description(8))
        self.source = source = Source(_arp_table_layout)

        # # #

        self.submodules.depacketizer = depacketizer = LiteEthARPDepacketizer()
        self.comb += Record.connect(sink, depacketizer.sink)

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            depacketizer.source.ack.eq(1),
            If(depacketizer.source.stb & depacketizer.source.sop,
                depacketizer.source.ack.eq(0),
                NextState("CHECK")
            )
        )
        valid = Signal()
        self.sync += valid.eq(
            depacketizer.source.stb &
            (depacketizer.source.hwtype == arp_hwtype_ethernet) &
            (depacketizer.source.proto == arp_proto_ip) &
            (depacketizer.source.hwsize == 6) &
            (depacketizer.source.protosize == 4) &
            (depacketizer.source.target_ip == ip_address)
        )
        reply = Signal()
        request = Signal()
        self.comb += Case(depacketizer.source.opcode, {
            arp_opcode_request: [request.eq(1)],
            arp_opcode_reply:   [reply.eq(1)],
            "default":          []
            })
        self.comb += [
            source.ip_address.eq(depacketizer.source.sender_ip),
            source.mac_address.eq(depacketizer.source.sender_mac)
        ]
        fsm.act("CHECK",
            If(valid,
                source.stb.eq(1),
                source.reply.eq(reply),
                source.request.eq(request)
            ),
            NextState("TERMINATE")
        ),
        fsm.act("TERMINATE",
            depacketizer.source.ack.eq(1),
            If(depacketizer.source.stb & depacketizer.source.eop,
                NextState("IDLE")
            )
        )


class LiteEthARPTable(Module):
    def __init__(self, clk_freq, max_requests=8):
        self.sink = sink = Sink(_arp_table_layout)             # from arp_rx
        self.source = source = Source(_arp_table_layout)       # to arp_tx

        # Request/Response interface
        self.request = request = Sink(arp_table_request_layout)
        self.response = response = Source(arp_table_response_layout)

        # # #

        request_timer = WaitTimer(clk_freq//10)
        request_counter = Counter(max=max_requests)
        request_pending = FlipFlop()
        request_ip_address = FlipFlop(32)
        self.submodules += request_timer, request_counter, request_pending, request_ip_address
        self.comb += [
            request_timer.wait.eq(request_pending.q & ~request_counter.ce),
            request_pending.d.eq(1),
            request_ip_address.d.eq(request.ip_address)
        ]

        # Note: Store only 1 IP/MAC couple, can be improved with a real
        # table in the future to improve performance when packets are
        # targeting multiple destinations.
        update = Signal()
        cached_valid = Signal()
        cached_ip_address = Signal(32)
        cached_mac_address = Signal(48)
        cached_timer = WaitTimer(clk_freq*10)
        self.submodules += cached_timer

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            # Note: for simplicicy, if APR table is busy response from arp_rx
            # is lost. This is compensated by the protocol (retries)
            If(sink.stb & sink.request,
                NextState("SEND_REPLY")
            ).Elif(sink.stb & sink.reply & request_pending.q,
                NextState("UPDATE_TABLE"),
            ).Elif(request_counter.value == max_requests-1,
                NextState("PRESENT_RESPONSE")
            ).Elif(request.stb | (request_pending.q & request_timer.done),
                NextState("CHECK_TABLE")
            )
        )
        fsm.act("SEND_REPLY",
            source.stb.eq(1),
            source.reply.eq(1),
            source.ip_address.eq(sink.ip_address),
            source.mac_address.eq(sink.mac_address),
            If(source.ack,
                NextState("IDLE")
            )
        )
        fsm.act("UPDATE_TABLE",
            request_pending.reset.eq(1),
            update.eq(1),
            NextState("CHECK_TABLE")
        )
        self.sync += \
            If(update,
                cached_valid.eq(1),
                cached_ip_address.eq(sink.ip_address),
                cached_mac_address.eq(sink.mac_address),
            ).Else(
                If(cached_timer.done,
                    cached_valid.eq(0)
                )
            )
        self.comb += cached_timer.wait.eq(~update)
        found = Signal()
        fsm.act("CHECK_TABLE",
            If(cached_valid,
                If(request_ip_address.q == cached_ip_address,
                    request_ip_address.reset.eq(1),
                    NextState("PRESENT_RESPONSE"),
                ).Elif(request.ip_address == cached_ip_address,
                    request.ack.eq(request.stb),
                    NextState("PRESENT_RESPONSE"),
                ).Else(
                    request_ip_address.ce.eq(request.stb),
                    NextState("SEND_REQUEST")
                )
            ).Else(
                request_ip_address.ce.eq(request.stb),
                NextState("SEND_REQUEST")
            )
        )
        fsm.act("SEND_REQUEST",
            source.stb.eq(1),
            source.request.eq(1),
            source.ip_address.eq(request_ip_address.q),
            If(source.ack,
                request_counter.reset.eq(request.stb),
                request_counter.ce.eq(1),
                request_pending.ce.eq(1),
                request.ack.eq(1),
                NextState("IDLE")
            )
        )
        self.comb += [
            If(request_counter == max_requests-1,
                response.failed.eq(1),
                request_counter.reset.eq(1),
                request_pending.reset.eq(1)
            ),
            response.mac_address.eq(cached_mac_address)
        ]
        fsm.act("PRESENT_RESPONSE",
            response.stb.eq(1),
            If(response.ack,
                NextState("IDLE")
            )
        )


class LiteEthARP(Module):
    def __init__(self, mac, mac_address, ip_address, clk_freq):
        self.submodules.tx = tx = LiteEthARPTX(mac_address, ip_address)
        self.submodules.rx = rx = LiteEthARPRX(mac_address, ip_address)
        self.submodules.table = table = LiteEthARPTable(clk_freq)
        self.comb += [
            Record.connect(rx.source, table.sink),
            Record.connect(table.source, tx.sink)
        ]
        mac_port = mac.crossbar.get_port(ethernet_type_arp)
        self.comb += [
            Record.connect(tx.source, mac_port.sink),
            Record.connect(mac_port.source, rx.sink)
        ]
