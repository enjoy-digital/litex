from litex.gen import *
from litex.gen.bank.description import *
from litex.gen.genlib.fsm import FSM, NextState


class SPIMaster(Module, AutoCSR):
    def __init__(self, pads, width=24, div=2, cpha=1):
        self.pads = pads

        self._ctrl = CSR()
        self._length = CSRStorage(8)
        self._status = CSRStatus()
        if hasattr(pads, "mosi"):
            self._mosi = CSRStorage(width)
        if hasattr(pads, "miso"):
            self._miso = CSRStatus(width)

        self.irq = Signal()

        ###

        # ctrl
        start = Signal()
        length = self._length.storage
        enable_cs = Signal()
        enable_shift = Signal()
        done = Signal()

        self.comb += [
            start.eq(self._ctrl.re & self._ctrl.r[0]),
            self._status.status.eq(done)
        ]

        # clk
        i = Signal(max=div)
        set_clk = Signal()
        clr_clk = Signal()
        self.sync += [
            If(set_clk,
                pads.clk.eq(enable_cs)
            ),
            If(clr_clk,
                pads.clk.eq(0),
                i.eq(0)
            ).Else(
                i.eq(i + 1),
            )
        ]

        self.comb += [
            set_clk.eq(i == (div//2-1)),
            clr_clk.eq(i == (div-1))
        ]

        # fsm
        cnt = Signal(8)
        clr_cnt = Signal()
        inc_cnt = Signal()
        self.sync += \
            If(clr_cnt,
                cnt.eq(0)
            ).Elif(inc_cnt,
                cnt.eq(cnt+1)
            )

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm
        fsm.act("IDLE",
            If(start,
                NextState("WAIT_CLK")
            ),
            done.eq(1),
            clr_cnt.eq(1)
        )
        fsm.act("WAIT_CLK",
            If(clr_clk,
                NextState("SHIFT")
            ),
        )
        fsm.act("SHIFT",
            If(cnt == length,
                NextState("END")
            ).Else(
                inc_cnt.eq(clr_clk),
            ),
            enable_cs.eq(1),
            enable_shift.eq(1),
        )
        fsm.act("END",
            If(set_clk,
                NextState("IDLE")
            ),
            enable_shift.eq(1),
            self.irq.eq(1)
        )

        # miso
        if hasattr(pads, "miso"):
            miso = Signal()
            sr_miso = Signal(width)

            # (cpha = 1: capture on clk falling edge)
            if cpha:
                self.sync += \
                    If(enable_shift,
                        If(clr_clk,
                            miso.eq(pads.miso),
                        ).Elif(set_clk,
                            sr_miso.eq(Cat(miso, sr_miso[:-1]))
                        )
                    )
            # (cpha = 0: capture on clk rising edge)
            else:
                self.sync += \
                    If(enable_shift,
                        If(set_clk,
                            miso.eq(pads.miso),
                        ).Elif(clr_clk,
                            sr_miso.eq(Cat(miso, sr_miso[:-1]))
                        )
                    )
            self.comb += self._miso.status.eq(sr_miso)

        # mosi
        if hasattr(pads, "mosi"):
            sr_mosi = Signal(width)

            # (cpha = 1: propagated on clk rising edge)
            if cpha:
                self.sync += \
                    If(start,
                        sr_mosi.eq(self._mosi.storage)
                    ).Elif(clr_clk & enable_shift,
                        sr_mosi.eq(Cat(Signal(), sr_mosi[:-1]))
                    ).Elif(set_clk,
                        pads.mosi.eq(sr_mosi[-1])
                    )

            # (cpha = 0: propagated on clk falling edge)
            else:
                self.sync += [
                    If(start,
                        sr_mosi.eq(self._mosi.storage)
                    ).Elif(set_clk & enable_shift,
                        sr_mosi.eq(Cat(Signal(), sr_mosi[:-1]))
                    ).Elif(clr_clk,
                        pads.mosi.eq(sr_mosi[-1])
                    )
                ]

        # cs_n
        self.comb += pads.cs_n.eq(~enable_cs)
