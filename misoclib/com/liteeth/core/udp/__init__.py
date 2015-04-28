from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.core.udp.crossbar import *


class LiteEthUDPPacketizer(Packetizer):
    def __init__(self):
        Packetizer.__init__(self,
            eth_udp_description(8),
            eth_ipv4_user_description(8),
            udp_header)


class LiteEthUDPTX(Module):
    def __init__(self, ip_address):
        self.sink = sink = Sink(eth_udp_user_description(8))
        self.source = source = Source(eth_ipv4_user_description(8))

        # # #

        self.submodules.packetizer = packetizer = LiteEthUDPPacketizer()
        self.comb += [
            packetizer.sink.stb.eq(sink.stb),
            packetizer.sink.sop.eq(sink.sop),
            packetizer.sink.eop.eq(sink.eop),
            sink.ack.eq(packetizer.sink.ack),
            packetizer.sink.src_port.eq(sink.src_port),
            packetizer.sink.dst_port.eq(sink.dst_port),
            packetizer.sink.length.eq(sink.length + udp_header.length),
            packetizer.sink.checksum.eq(0),  # Disabled (MAC CRC is enough)
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
            source.length.eq(packetizer.sink.length),
            source.protocol.eq(udp_protocol),
            source.ip_address.eq(sink.ip_address),
            If(source.stb & source.eop & source.ack,
                NextState("IDLE")
            )
        )


class LiteEthUDPDepacketizer(Depacketizer):
    def __init__(self):
        Depacketizer.__init__(self,
            eth_ipv4_user_description(8),
            eth_udp_description(8),
            udp_header)


class LiteEthUDPRX(Module):
    def __init__(self, ip_address):
        self.sink = sink = Sink(eth_ipv4_user_description(8))
        self.source = source = Source(eth_udp_user_description(8))

        # # #

        self.submodules.depacketizer = depacketizer = LiteEthUDPDepacketizer()
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
            (sink.protocol == udp_protocol)
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
            source.src_port.eq(depacketizer.source.src_port),
            source.dst_port.eq(depacketizer.source.dst_port),
            source.ip_address.eq(sink.ip_address),
            source.length.eq(depacketizer.source.length - udp_header.length),
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


class LiteEthUDP(Module):
    def __init__(self, ip, ip_address):
        self.submodules.tx = tx = LiteEthUDPTX(ip_address)
        self.submodules.rx = rx = LiteEthUDPRX(ip_address)
        ip_port = ip.crossbar.get_port(udp_protocol)
        self.comb += [
            Record.connect(tx.source, ip_port.sink),
            Record.connect(ip_port.source, rx.sink)
        ]
        self.submodules.crossbar = crossbar = LiteEthUDPCrossbar()
        self.comb += [
            Record.connect(crossbar.master.source, tx.sink),
            Record.connect(rx.source, crossbar.master.sink)
        ]
