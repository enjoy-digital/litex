from misoclib.mem.litesata.common import *


class K7LiteSATAPHYCRG(Module):
    def __init__(self, pads, gtx, revision, clk_freq):
        self.tx_reset = Signal()
        self.rx_reset = Signal()
        self.ready = Signal()

        self.clock_domains.cd_sata_tx = ClockDomain()
        self.clock_domains.cd_sata_rx = ClockDomain()

        # CPLL
        #   (sata_gen3) 150MHz / VCO @ 3GHz / Line rate @ 6Gbps
        #   (sata_gen2 & sata_gen1) VCO still @ 3 GHz, Line rate is
        #   decreased with output dividers.
        refclk = Signal()
        self.specials += Instance("IBUFDS_GTE2",
            i_CEB=0,
            i_I=pads.refclk_p,
            i_IB=pads.refclk_n,
            o_O=refclk
        )
        self.comb += gtx.gtrefclk0.eq(refclk)

        # TX clocking
        #   (sata_gen3) 150MHz from CPLL TXOUTCLK, sata_tx clk @ 300MHz (16-bits)
        #   (sata_gen2) 150MHz from CPLL TXOUTCLK, sata_tx clk @ 150MHz (16-bits)
        #   (sata_gen1) 150MHz from CPLL TXOUTCLK, sata_tx clk @ 75MHz (16-bits)
        mmcm_reset = Signal()
        mmcm_locked = Signal()
        mmcm_fb = Signal()
        mmcm_clk_i = Signal()
        mmcm_clk0_o = Signal()
        mmcm_div_config = {
            "sata_gen1":   16.0,
            "sata_gen2":    8.0,
            "sata_gen3":    4.0
            }
        mmcm_div = mmcm_div_config[revision]
        self.specials += [
            Instance("BUFG", i_I=gtx.txoutclk, o_O=mmcm_clk_i),
            Instance("MMCME2_ADV",
                p_BANDWIDTH="HIGH", p_COMPENSATION="ZHOLD", i_RST=mmcm_reset, o_LOCKED=mmcm_locked,

                # DRP
                i_DCLK=0, i_DEN=0, i_DWE=0, #o_DRDY=,
                i_DADDR=0, i_DI=0, #o_DO=,

                # VCO
                p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=6.666,
                p_CLKFBOUT_MULT_F=8.000, p_CLKFBOUT_PHASE=0.000, p_DIVCLK_DIVIDE=1,
                i_CLKIN1=mmcm_clk_i, i_CLKFBIN=mmcm_fb, o_CLKFBOUT=mmcm_fb,

                # CLK0
                p_CLKOUT0_DIVIDE_F=mmcm_div, p_CLKOUT0_PHASE=0.000, o_CLKOUT0=mmcm_clk0_o,
            ),
            Instance("BUFG", i_I=mmcm_clk0_o, o_O=self.cd_sata_tx.clk),
        ]
        self.comb += [
            gtx.txusrclk.eq(self.cd_sata_tx.clk),
            gtx.txusrclk2.eq(self.cd_sata_tx.clk)
        ]

        # RX clocking
        #   (sata_gen3) sata_rx recovered clk @ 300MHz from GTX RXOUTCLK
        #   (sata_gen2) sata_rx recovered clk @ 150MHz from GTX RXOUTCLK
        #   (sata_gen1) sata_rx recovered clk @ 150MHz from GTX RXOUTCLK
        self.specials += [
            Instance("BUFG", i_I=gtx.rxoutclk, o_O=self.cd_sata_rx.clk),
        ]
        self.comb += [
            gtx.rxusrclk.eq(self.cd_sata_rx.clk),
            gtx.rxusrclk2.eq(self.cd_sata_rx.clk)
        ]

        # Configuration Reset
        #   After configuration, GTX's resets have to stay low for at least 500ns
        #   See AR43482
        startup_cycles = math.ceil(500*clk_freq/1000000000)
        startup_wait = Timeout(startup_cycles)
        self.submodules += startup_wait
        self.comb += [
            startup_wait.reset.eq(self.tx_reset | self.rx_reset),
            startup_wait.ce.eq(1)
        ]

        # TX Startup FSM
        self.tx_ready = Signal()
        tx_startup_fsm = InsertReset(FSM(reset_state="IDLE"))
        self.submodules += tx_startup_fsm
        # Wait 500ns of AR43482
        tx_startup_fsm.act("IDLE",
            If(startup_wait.reached,
                NextState("RESET_ALL"),
            )
        )
        # Reset CPLL, MMCM, GTX
        tx_startup_fsm.act("RESET_ALL",
            gtx.cpllreset.eq(1),
            mmcm_reset.eq(1),
            gtx.gttxreset.eq(1),
            NextState("RELEASE_CPLL"),
        )
        # Release CPLL reset and wait for lock
        tx_startup_fsm.act("RELEASE_CPLL",
            mmcm_reset.eq(1),
            gtx.gttxreset.eq(1),
            If(gtx.cplllock,
                NextState("RELEASE_MMCM"),
            )
        )
        # Release MMCM reset and wait for lock
        tx_startup_fsm.act("RELEASE_MMCM",
            gtx.gttxreset.eq(1),
            If(mmcm_locked,
                NextState("RELEASE_GTX")
            )
        )
        # Release GTX reset and wait for GTX resetdone
        # (from UG476, GTX is reseted on falling edge
        # of gttxreset)
        tx_startup_fsm.act("RELEASE_GTX",
            gtx.txuserrdy.eq(1),
            If(gtx.txresetdone,
                NextState("READY")
            )
        )
        # Start Delay alignment (Pulse)
        tx_startup_fsm.act("ALIGN",
            gtx.txuserrdy.eq(1),
            gtx.txdlyreset.eq(1),
            NextState("WAIT_ALIGN")
        )
        # Wait Delay alignment
        tx_startup_fsm.act("WAIT_ALIGN",
            gtx.txuserrdy.eq(1),
            If(gtx.txdlyresetdone,
                NextState("READY")
            )
        )
        tx_startup_fsm.act("READY",
            gtx.txuserrdy.eq(1),
            self.tx_ready.eq(1)
        )

        tx_ready_timeout = Timeout(1*clk_freq//1000)
        self.submodules += tx_ready_timeout
        self.comb += [
            tx_ready_timeout.reset.eq(self.tx_reset | self.tx_ready),
            tx_ready_timeout.ce.eq(~self.tx_ready),
            tx_startup_fsm.reset.eq(self.tx_reset | tx_ready_timeout.reached),
        ]


        # RX Startup FSM
        self.rx_ready = Signal()
        rx_startup_fsm = InsertReset(FSM(reset_state="IDLE"))
        self.submodules += rx_startup_fsm

        cdr_stable = Timeout(2048)
        self.submodules += cdr_stable
        self.comb += cdr_stable.ce.eq(1),

        # Wait 500ns of AR43482
        rx_startup_fsm.act("IDLE",
            cdr_stable.reset.eq(1),
            If(startup_wait.reached,
                NextState("RESET_GTX"),
            )
        )
        # Reset GTX
        rx_startup_fsm.act("RESET_GTX",
            gtx.gtrxreset.eq(1),
            NextState("WAIT_CPLL")
        )
        # Wait for CPLL lock
        rx_startup_fsm.act("WAIT_CPLL",
            gtx.gtrxreset.eq(1),
            If(gtx.cplllock,
                NextState("RELEASE_GTX"),
                cdr_stable.reset.eq(1)
            )
        )
        # Release GTX reset and wait for GTX resetdone
        # (from UG476, GTX is reseted on falling edge
        # of gttxreset)
        rx_startup_fsm.act("RELEASE_GTX",
            gtx.rxuserrdy.eq(1),
            If(gtx.rxresetdone &  cdr_stable.reached,
                NextState("ALIGN")
            )
        )
        # Start Delay alignment (Pulse)
        rx_startup_fsm.act("ALIGN",
            gtx.rxuserrdy.eq(1),
            gtx.rxdlyreset.eq(1),
            NextState("WAIT_ALIGN")
        )
        # Wait Delay alignment
        rx_startup_fsm.act("WAIT_ALIGN",
            gtx.rxuserrdy.eq(1),
            If(gtx.rxdlyresetdone,
                NextState("READY")
            )
        )
        rx_startup_fsm.act("READY",
            gtx.rxuserrdy.eq(1),
            self.rx_ready.eq(1)
        )

        rx_ready_timeout = Timeout(1*clk_freq//1000)
        self.submodules += rx_ready_timeout
        self.comb += [
            rx_ready_timeout.reset.eq(self.rx_reset | self.rx_ready),
            rx_ready_timeout.ce.eq(~self.rx_ready),
            rx_startup_fsm.reset.eq(self.rx_reset | rx_ready_timeout.reached),
        ]

        # Ready
        self.comb += self.ready.eq(self.tx_ready & self.rx_ready)

        # Reset for SATA TX/RX clock domains
        self.specials += [
            AsyncResetSynchronizer(self.cd_sata_tx, ~(gtx.cplllock & mmcm_locked) | self.tx_reset),
            AsyncResetSynchronizer(self.cd_sata_rx, ~gtx.cplllock | self.rx_reset),
        ]
