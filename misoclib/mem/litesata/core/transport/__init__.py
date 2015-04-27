from misoclib.mem.litesata.common import *


def test_type(name, signal):
    return signal == fis_types[name]


class LiteSATATransportTX(Module):
    def __init__(self, link):
        self.sink = sink = Sink(transport_tx_description(32))

        # # #

        cmd_ndwords = max(fis_reg_h2d_header.length,
                          fis_data_header.length)
        encoded_cmd = Signal(cmd_ndwords*32)

        counter = Counter(max=cmd_ndwords+1)
        self.submodules += counter

        cmd_len = Signal(counter.width)
        cmd_with_data = Signal()

        cmd_send = Signal()
        data_send = Signal()
        cmd_done = Signal()

        fis_type = Signal(8)
        update_fis_type = Signal()

        def test_type_tx(name):
            return test_type(name, sink.type)

        self.fsm = fsm = FSM(reset_state="IDLE")
        self.submodules += fsm
        fsm.act("IDLE",
            sink.ack.eq(0),
            counter.reset.eq(1),
            update_fis_type.eq(1),
            If(sink.stb & sink.sop,
                If(test_type_tx("REG_H2D"),
                    NextState("SEND_CTRL_CMD")
                ).Elif(test_type_tx("DATA"),
                    NextState("SEND_DATA_CMD")
                ).Else(
                    sink.ack.eq(1)
                )
            ).Else(
                sink.ack.eq(1)
            )
        )
        self.sync += \
            If(update_fis_type, fis_type.eq(link.source.d[:8]))

        fsm.act("SEND_CTRL_CMD",
            fis_reg_h2d_header.encode(sink, encoded_cmd),
            cmd_len.eq(fis_reg_h2d_header.length-1),
            cmd_send.eq(1),
            If(cmd_done,
                sink.ack.eq(1),
                NextState("IDLE")
            )
        )
        fsm.act("SEND_DATA_CMD",
            sink.ack.eq(0),
            fis_data_header.encode(sink, encoded_cmd),
            cmd_len.eq(fis_data_header.length-1),
            cmd_with_data.eq(1),
            cmd_send.eq(1),
            If(cmd_done,
                NextState("SEND_DATA")
            )
        )
        fsm.act("SEND_DATA",
            data_send.eq(1),
            sink.ack.eq(link.sink.ack),
            If(sink.stb & sink.eop & sink.ack,
                NextState("IDLE")
            )
        )

        cmd_cases = {}
        for i in range(cmd_ndwords):
            cmd_cases[i] = [link.sink.d.eq(encoded_cmd[32*i:32*(i+1)])]

        self.comb += [
            counter.ce.eq(sink.stb & link.sink.ack),
            cmd_done.eq((counter.value == cmd_len) &
                        link.sink.stb &
                        link.sink.ack),
            If(cmd_send,
                link.sink.stb.eq(sink.stb),
                link.sink.sop.eq(counter.value == 0),
                link.sink.eop.eq((counter.value == cmd_len) & ~cmd_with_data),
                Case(counter.value, cmd_cases)
            ).Elif(data_send,
                link.sink.stb.eq(sink.stb),
                link.sink.sop.eq(0),
                link.sink.eop.eq(sink.eop),
                link.sink.d.eq(sink.data)
            )
        ]


class LiteSATATransportRX(Module):
    def __init__(self, link):
        self.source = source = Source(transport_rx_description(32))

        # # #

        cmd_ndwords = max(fis_reg_d2h_header.length,
                          fis_dma_activate_d2h_header.length,
                          fis_pio_setup_d2h_header.length,
                          fis_data_header.length)
        encoded_cmd = Signal(cmd_ndwords*32)

        counter = Counter(max=cmd_ndwords+1)
        self.submodules += counter

        cmd_len = Signal(counter.width)

        cmd_receive = Signal()
        data_receive = Signal()
        cmd_done = Signal()
        data_done = Signal()

        def test_type_rx(name):
            return test_type(name, link.source.d[:8])

        self.fsm = fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        data_sop = Signal()
        fis_type = Signal(8)
        update_fis_type = Signal()

        fsm.act("IDLE",
            link.source.ack.eq(0),
            counter.reset.eq(1),
            update_fis_type.eq(1),
            If(link.source.stb & link.source.sop,
                If(test_type_rx("REG_D2H"),
                    NextState("RECEIVE_CTRL_CMD")
                ).Elif(test_type_rx("DMA_ACTIVATE_D2H"),
                    NextState("RECEIVE_CTRL_CMD")
                ).Elif(test_type_rx("PIO_SETUP_D2H"),
                    NextState("RECEIVE_CTRL_CMD")
                ).Elif(test_type_rx("DATA"),
                    NextState("RECEIVE_DATA_CMD"),
                ).Else(
                    link.source.ack.eq(1)
                )
            ).Else(
                link.source.ack.eq(1)
            )
        )
        self.sync += \
            If(update_fis_type, fis_type.eq(link.source.d[:8]))

        fsm.act("RECEIVE_CTRL_CMD",
            If(test_type("REG_D2H", fis_type),
                cmd_len.eq(fis_reg_d2h_header.length-1)
            ).Elif(test_type("DMA_ACTIVATE_D2H", fis_type),
                cmd_len.eq(fis_dma_activate_d2h_header.length-1)
            ).Else(
                cmd_len.eq(fis_pio_setup_d2h_header.length-1)
            ),
            cmd_receive.eq(1),
            link.source.ack.eq(1),
            If(cmd_done,
                NextState("PRESENT_CTRL_CMD")
            )
        )
        fsm.act("PRESENT_CTRL_CMD",
            source.stb.eq(1),
            source.sop.eq(1),
            source.eop.eq(1),
            If(test_type("REG_D2H", fis_type),
                fis_reg_d2h_header.decode(encoded_cmd, source)
            ).Elif(test_type("DMA_ACTIVATE_D2H", fis_type),
                fis_dma_activate_d2h_header.decode(encoded_cmd, source)
            ).Else(
                fis_pio_setup_d2h_header.decode(encoded_cmd, source)
            ),
            If(source.stb & source.ack,
                NextState("IDLE")
            )
        )
        fsm.act("RECEIVE_DATA_CMD",
            cmd_len.eq(fis_data_header.length-1),
            cmd_receive.eq(1),
            link.source.ack.eq(1),
            If(cmd_done,
                NextState("PRESENT_DATA")
            )
        )
        fsm.act("PRESENT_DATA",
            data_receive.eq(1),
            source.stb.eq(link.source.stb),
            fis_data_header.decode(encoded_cmd, source),
            source.sop.eq(data_sop),
            source.eop.eq(link.source.eop),
            source.error.eq(link.source.error),
            source.data.eq(link.source.d),
            link.source.ack.eq(source.ack),
            If(source.stb & source.eop & source.ack,
                NextState("IDLE")
            )
        )

        self.sync += \
            If(fsm.ongoing("RECEIVE_DATA_CMD"),
                data_sop.eq(1)
            ).Elif(fsm.ongoing("PRESENT_DATA"),
                If(source.stb & source.ack,
                    data_sop.eq(0)
                )
            )

        cmd_cases = {}
        for i in range(cmd_ndwords):
            cmd_cases[i] = [encoded_cmd[32*i:32*(i+1)].eq(link.source.d)]

        self.comb += \
            If(cmd_receive & link.source.stb,
                counter.ce.eq(1)
            )
        self.sync += \
            If(cmd_receive,
                Case(counter.value, cmd_cases),
            )
        self.comb += cmd_done.eq((counter.value == cmd_len) & link.source.ack)


class LiteSATATransport(Module):
    def __init__(self, link):
        self.submodules.tx = LiteSATATransportTX(link)
        self.submodules.rx = LiteSATATransportRX(link)
        self.sink, self.source = self.tx.sink, self.rx.source
