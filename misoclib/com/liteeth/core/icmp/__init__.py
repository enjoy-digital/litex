from misoclib.com.liteeth.common import *


class LiteEthICMPPacketizer(Packetizer):
    def __init__(self):
        Packetizer.__init__(self,
            eth_icmp_description(8),
            eth_ipv4_user_description(8),
            icmp_header)


class LiteEthICMPTX(Module):
    def __init__(self, ip_address):
        self.sink = sink = Sink(eth_icmp_user_description(8))
        self.source = source = Source(eth_ipv4_user_description(8))

        # # #

        self.submodules.packetizer = packetizer = LiteEthICMPPacketizer()
        self.comb += [
            packetizer.sink.stb.eq(sink.stb),
            packetizer.sink.sop.eq(sink.sop),
            packetizer.sink.eop.eq(sink.eop),
            sink.ack.eq(packetizer.sink.ack),
            packetizer.sink.msgtype.eq(sink.msgtype),
            packetizer.sink.code.eq(sink.code),
            packetizer.sink.checksum.eq(sink.checksum),
            packetizer.sink.quench.eq(sink.quench),
            packetizer.sink.data.eq(sink.data)
        ]

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            packetizer.source.ack.eq(1),
            If(packetizer.source.stb & packetizer.source.sop,
                packetizer.source.ack.eq(0),
                NextState("SEND")
            )
        )
        fsm.act("SEND",
            Record.connect(packetizer.source, source),
            source.length.eq(sink.length + icmp_header.length),
            source.protocol.eq(icmp_protocol),
            source.ip_address.eq(sink.ip_address),
            If(source.stb & source.eop & source.ack,
                NextState("IDLE")
            )
        )


class LiteEthICMPDepacketizer(Depacketizer):
    def __init__(self):
        Depacketizer.__init__(self,
            eth_ipv4_user_description(8),
            eth_icmp_description(8),
            icmp_header)


class LiteEthICMPRX(Module):
    def __init__(self, ip_address):
        self.sink = sink = Sink(eth_ipv4_user_description(8))
        self.source = source = Source(eth_icmp_user_description(8))

        # # #

        self.submodules.depacketizer = depacketizer = LiteEthICMPDepacketizer()
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
            (sink.protocol == icmp_protocol)
        )
        fsm.act("CHECK",
            If(valid,
                NextState("PRESENT")
            ).Else(
                NextState("DROP")
            )
        )
        self.comb += [
            source.sop.eq(depacketizer.source.sop),
            source.eop.eq(depacketizer.source.eop),
            source.msgtype.eq(depacketizer.source.msgtype),
            source.code.eq(depacketizer.source.code),
            source.checksum.eq(depacketizer.source.checksum),
            source.quench.eq(depacketizer.source.quench),
            source.ip_address.eq(sink.ip_address),
            source.length.eq(sink.length - icmp_header.length),
            source.data.eq(depacketizer.source.data),
            source.error.eq(depacketizer.source.error)
        ]
        fsm.act("PRESENT",
            source.stb.eq(depacketizer.source.stb),
            depacketizer.source.ack.eq(source.ack),
            If(source.stb & source.eop & source.ack,
                NextState("IDLE")
            )
        )
        fsm.act("DROP",
            depacketizer.source.ack.eq(1),
            If(depacketizer.source.stb &
               depacketizer.source.eop &
               depacketizer.source.ack,
                NextState("IDLE")
            )
        )


class LiteEthICMPEcho(Module):
    def __init__(self):
        self.sink = sink = Sink(eth_icmp_user_description(8))
        self.source = source = Source(eth_icmp_user_description(8))

        # # #

        self.submodules.buffer = Buffer(eth_icmp_user_description(8), 128, 2)
        self.comb += [
            Record.connect(sink, self.buffer.sink),
            Record.connect(self.buffer.source, source),
            self.source.msgtype.eq(0x0),
            self.source.checksum.eq(~((~self.buffer.source.checksum)-0x0800))
        ]


class LiteEthICMP(Module):
    def __init__(self, ip, ip_address):
        self.submodules.tx = tx = LiteEthICMPTX(ip_address)
        self.submodules.rx = rx = LiteEthICMPRX(ip_address)
        self.submodules.echo = echo = LiteEthICMPEcho()
        self.comb += [
            Record.connect(rx.source, echo.sink),
            Record.connect(echo.source, tx.sink)
        ]
        ip_port = ip.crossbar.get_port(icmp_protocol)
        self.comb += [
            Record.connect(tx.source, ip_port.sink),
            Record.connect(ip_port.source, rx.sink)
        ]
