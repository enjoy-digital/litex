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

        retry_timer = WaitTimer(self.us(10000))
        align_timer = WaitTimer(self.us(873))
        self.submodules += align_timer, retry_timer

        align_det = Signal()
        misalign_det = Signal()
        non_align_counter = Counter(4)
        self.submodules += non_align_counter

        self.comb +=  [
            If(sink.stb,
                align_det.eq((self.sink.charisk == 0b0001) &
                                (self.sink.data == primitives["ALIGN"])),
                misalign_det.eq((self.sink.charisk & 0b1010) != 0)
            )
        ]

        self.fsm = fsm = InsertReset(FSM(reset_state="RESET"))
        self.submodules += fsm
        self.comb += fsm.reset.eq(retry_timer.done | align_timer.done)
        fsm.act("RESET",
            trx.tx_idle.eq(1),
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
            retry_timer.wait.eq(1),
            If(trx.rx_cominit_stb,
                NextState("AWAIT_NO_COMINIT")
            )
        )
        fsm.act("AWAIT_NO_COMINIT",
            trx.tx_idle.eq(1),
            retry_timer.wait.eq(1),
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
            retry_timer.wait.eq(1),
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
            align_timer.wait.eq(1),
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
            align_timer.wait.eq(1),
            If(align_det & ~trx.rx_idle,
                NextState("SEND_ALIGN")
            )
        )
        fsm.act("SEND_ALIGN",
            trx.tx_idle.eq(0),
            trx.rx_align.eq(1),
            align_timer.wait.eq(1),
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

        # wait alignement stability for 100ms before declaring ctrl is ready,
        # reset the RX part of the transceiver when misalignment is detected.
        stability_timer = WaitTimer(100*clk_freq//1000)
        self.submodules += stability_timer

        fsm.act("READY",
            trx.tx_idle.eq(0),
            trx.rx_align.eq(1),
            source.data.eq(primitives["SYNC"]),
            source.charisk.eq(0b0001),
            stability_timer.wait.eq(1),
            self.ready.eq(stability_timer.done),
            If(trx.rx_idle,
                NextState("RESET"),
            ).Elif(misalign_det,
                crg.rx_reset.eq(1),
                NextState("REALIGN")
            )
        )
        fsm.act("REALIGN",
            If(crg.ready,
                NextState("READY")
            )
        )



    def us(self, t):
        clk_period_us = 1000000/self.clk_freq
        return math.ceil(t/clk_period_us)
