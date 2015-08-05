# RGMII PHY for Spartan-6

from migen.genlib.io import DDROutput
from migen.genlib.misc import WaitTimer
from migen.genlib.fsm import FSM, NextState

from misoclib.com.liteeth.common import *


class LiteEthPHYRGMIITX(Module):
    def __init__(self, pads, pads_register=True):
        self.sink = sink = Sink(eth_phy_description(8))

        # # #

        self.specials += Instance("ODDR2",
                p_DDR_ALIGNMENT="C0", p_INIT=0, p_SRTYPE="ASYNC",
                i_C0=ClockSignal("eth_tx"), i_C1=~ClockSignal("eth_tx"),
                i_CE=1, i_S=0, i_R=0,
                i_D0=sink.stb, i_D1=sink.stb, o_Q=pads.tx_ctl,
        )
        for i in range(4):
            self.specials += Instance("ODDR2",
                    p_DDR_ALIGNMENT="C0", p_INIT=0, p_SRTYPE="ASYNC",
                    i_C0=ClockSignal("eth_tx"), i_C1=~ClockSignal("eth_tx"),
                    i_CE=1, i_S=0, i_R=0,
                    i_D0=sink.data[i], i_D1=sink.data[4+i], o_Q=pads.tx_data[i],
            )
        self.comb += sink.ack.eq(1)


class LiteEthPHYRGMIIRX(Module):
    def __init__(self, pads):
        self.source = source = Source(eth_phy_description(8))

        # # #

        rx_ctl = Signal()
        rx_data = Signal(8)

        self.specials += Instance("IDDR2",
                p_DDR_ALIGNMENT="C0", p_INIT_Q0=0, p_INIT_Q1=0, p_SRTYPE="ASYNC",
                i_C0=ClockSignal("eth_rx"), i_C1=~ClockSignal("eth_rx"),
                i_CE=1, i_S=0, i_R=0,
                i_D=pads.rx_ctl, o_Q1=rx_ctl,
        )
        for i in range(4):
            self.specials += Instance("IDDR2",
                    p_DDR_ALIGNMENT="C0", p_INIT_Q0=0, p_INIT_Q1=0, p_SRTYPE="ASYNC",
                    i_C0=ClockSignal("eth_rx"), i_C1=~ClockSignal("eth_rx"),
                    i_CE=1, i_S=0, i_R=0,
                    i_D=pads.rx_data[i], o_Q0=rx_data[4+i], o_Q1=rx_data[i],
            )


        rx_ctl_d = Signal()
        self.sync += rx_ctl_d.eq(rx_ctl)

        sop = Signal()
        eop = Signal()
        self.comb += [
            sop.eq(rx_ctl & ~rx_ctl_d),
            eop.eq(~rx_ctl & rx_ctl_d)
        ]
        self.sync += [
            source.stb.eq(rx_ctl),
            source.sop.eq(sop),
            source.data.eq(rx_data)
        ]
        self.comb += source.eop.eq(eop)


class LiteEthPHYRGMIICRG(Module, AutoCSR):
    def __init__(self, clock_pads, pads, with_hw_init_reset):
        self._reset = CSRStorage()

        # # #

        self.clock_domains.cd_eth_rx = ClockDomain()
        self.clock_domains.cd_eth_tx = ClockDomain()


        # RX
        dcm_reset = Signal()
        dcm_locked = Signal()

        timer = WaitTimer(1024)
        fsm = FSM(reset_state="DCM_RESET")
        self.submodules += timer, fsm

        fsm.act("DCM_RESET",
            dcm_reset.eq(1),
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                NextState("DCM_WAIT")
            )
        )
        fsm.act("DCM_WAIT",
            timer.wait.eq(1),
            If(timer.done,
                NextState("DCM_CHECK_LOCK")
            )
        )
        fsm.act("DCM_CHECK_LOCK",
            If(~dcm_locked,
                NextState("DCM_RESET")
            )
        )

        clk90_rx = Signal()
        clk0_rx = Signal()
        clk0_rx_bufg = Signal()
        self.specials += Instance("DCM",
                i_CLKIN=clock_pads.rx,
                i_CLKFB=clk0_rx_bufg,
                o_CLK0=clk0_rx,
                o_CLK90=clk90_rx,
                o_LOCKED=dcm_locked,
                i_PSEN=0,
                i_PSCLK=0,
                i_PSINCDEC=0,
                i_RST=dcm_reset
        )

        self.specials += Instance("BUFG", i_I=clk0_rx, o_O=clk0_rx_bufg)
        self.specials += Instance("BUFG", i_I=clk90_rx, o_O=self.cd_eth_rx.clk)

        # TX
        self.specials += DDROutput(1, 0, clock_pads.tx, ClockSignal("eth_tx"))
        self.specials += Instance("BUFG", i_I=self.cd_eth_rx.clk, o_O=self.cd_eth_tx.clk)

        # Reset
        if with_hw_init_reset:
            reset = Signal()
            counter_done = Signal()
            self.submodules.counter = counter = Counter(max=512)
            self.comb += [
                counter_done.eq(counter.value == 256),
                counter.ce.eq(~counter_done),
                reset.eq(~counter_done | self._reset.storage)
            ]
        else:
            reset = self._reset.storage
        self.comb += pads.rst_n.eq(~reset)
        self.specials += [
            AsyncResetSynchronizer(self.cd_eth_tx, reset),
            AsyncResetSynchronizer(self.cd_eth_rx, reset),
        ]


class LiteEthPHYRGMII(Module, AutoCSR):
    def __init__(self, clock_pads, pads, with_hw_init_reset=True):
        self.dw = 8
        self.submodules.crg = LiteEthPHYRGMIICRG(clock_pads,
                                                 pads,
                                                 with_hw_init_reset)
        self.submodules.tx = RenameClockDomains(LiteEthPHYRGMIITX(pads),
                                                "eth_tx")
        self.submodules.rx = RenameClockDomains(LiteEthPHYRGMIIRX(pads),
                                                "eth_rx")
        self.sink, self.source = self.tx.sink, self.rx.source
