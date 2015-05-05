from misoclib.mem.litesata.common import *


class LiteSATAPHYCtrl(Module):
    def __init__(self, trx, crg, clk_freq):
        self.clk_freq = clk_freq
        self.ready = Signal()
        self.sink = sink = Sink(phy_description(32))
        self.source = source = Source(phy_description(32))

        # # #

        self.comb += [
            source.stb.eq(1),
            sink.ack.eq(1)
        ]

        retry_timeout = Timeout(self.us(10000))
        align_timeout = Timeout(self.us(873))
        self.submodules += align_timeout, retry_timeout

        align_detect = Signal()
        non_align_cnt = Signal(4)
        non_align_counter = Counter(4)
        self.submodules += non_align_counter

        self.fsm = fsm = InsertReset(FSM(reset_state="RESET"))
        self.submodules += fsm
        self.comb += fsm.reset.eq(retry_timeout.reached | align_timeout.reached)
        fsm.act("RESET",
            trx.tx_idle.eq(1),
            retry_timeout.reset.eq(1),
            align_timeout.reset.eq(1),
            non_align_counter.reset.eq(1),
            If(crg.ready,
                NextState("COMINIT")
            )
        )
        fsm.act("COMINIT",
            trx.tx_idle.eq(1),
            trx.tx_cominit_stb.eq(1),
            If(trx.tx_cominit_ack & ~trx.rx_cominit_stb,
                NextState("AWAIT_COMINIT")
            )
        )
        fsm.act("AWAIT_COMINIT",
            trx.tx_idle.eq(1),
            retry_timeout.ce.eq(1),
            If(trx.rx_cominit_stb,
                NextState("AWAIT_NO_COMINIT")
            )
        )
        fsm.act("AWAIT_NO_COMINIT",
            trx.tx_idle.eq(1),
            retry_timeout.reset.eq(1),
            If(~trx.rx_cominit_stb,
                NextState("CALIBRATE")
            )
        )
        fsm.act("CALIBRATE",
            trx.tx_idle.eq(1),
            NextState("COMWAKE"),
        )
        fsm.act("COMWAKE",
            trx.tx_idle.eq(1),
            trx.tx_comwake_stb.eq(1),
            If(trx.tx_comwake_ack,
                NextState("AWAIT_COMWAKE")
            )
        )
        fsm.act("AWAIT_COMWAKE",
            trx.tx_idle.eq(1),
            retry_timeout.ce.eq(1),
            If(trx.rx_comwake_stb,
                NextState("AWAIT_NO_COMWAKE")
            )
        )
        fsm.act("AWAIT_NO_COMWAKE",
            trx.tx_idle.eq(1),
            If(~trx.rx_comwake_stb,
                NextState("AWAIT_NO_RX_IDLE")
            )
        )
        fsm.act("AWAIT_NO_RX_IDLE",
            trx.tx_idle.eq(0),
            source.data.eq(0x4A4A4A4A),  # D10.2
            source.charisk.eq(0b0000),
            align_timeout.ce.eq(1),
            If(~trx.rx_idle,
                NextState("AWAIT_ALIGN"),
                crg.tx_reset.eq(1),
                crg.rx_reset.eq(1)
            )
        )
        fsm.act("AWAIT_ALIGN",
            trx.tx_idle.eq(0),
            source.data.eq(0x4A4A4A4A),  # D10.2
            source.charisk.eq(0b0000),
            trx.rx_align.eq(1),
            align_timeout.ce.eq(1),
            If(align_detect & ~trx.rx_idle,
                NextState("SEND_ALIGN")
            )
        )
        fsm.act("SEND_ALIGN",
            trx.tx_idle.eq(0),
            trx.rx_align.eq(1),
            align_timeout.ce.eq(1),
            source.data.eq(primitives["ALIGN"]),
            source.charisk.eq(0b0001),
            If(sink.stb,
               If(sink.data[0:8] == 0x7C,
                   non_align_counter.ce.eq(1)
               ).Else(
                   non_align_counter.reset.eq(1)
               )
            ),
            If(non_align_counter.value == 3,
                NextState("READY")
            )
        )
        fsm.act("READY",
            trx.tx_idle.eq(0),
            trx.rx_align.eq(1),
            source.data.eq(primitives["SYNC"]),
            source.charisk.eq(0b0001),
            self.ready.eq(1),
            If(trx.rx_idle,
               NextState("RESET"),
			)
        )

        self.comb +=  align_detect.eq(self.sink.stb &
                                     (self.sink.data == primitives["ALIGN"]))

    def us(self, t):
        clk_period_us = 1000000/self.clk_freq
        return math.ceil(t/clk_period_us)
