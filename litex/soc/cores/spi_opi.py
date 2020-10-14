#
# This file is part of LiteX.
#
# Copyright (c) 2020 bunnie <bunnie@kosagi.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen.genlib.cdc import MultiReg

from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr_eventmanager import *

from litex.soc.integration.doc import AutoDoc, ModuleDoc


class S7SPIOPI(Module, AutoCSR, AutoDoc):
    def __init__(self, pads,
        dq_delay_taps  = 31,
        sclk_name      = "SCLK_ODDR",
        iddr_name      = "SPI_IDDR",
        cipo_name      = "CIPO_FDRE",
        sim            = False,
        spiread        = False,
        prefetch_lines = 1):
        self.intro = ModuleDoc("""Intro

        SpiOpi implements a dual-mode SPI or OPI interface. OPI is an octal (8-bit) wide variant of
        SPI, which is unique to Macronix parts. It is concurrently interoperable with SPI. The chip
        supports "DTR mode" (double transfer rate, e.g. DDR) where data is transferred on each edge
        of the clock, and there is a source-synchronous DQS associated with the input data.

        The chip by default boots into SPI-only mode (unless NV bits are burned otherwise) so to
        enable OPI, a config register needs to be written with SPI mode. Note that once the config
        register is written, the only way to return to SPI mode is to change it with OPI writes, or
        to issue a hardware reset. This has major implications for reconfiguring the FPGA: a simple
        JTAG command to reload from SPI will not yank PROG_B low, and so the SPI ROM will be in DOPI,
        and SPI loading will fail. Thus, system architects must take into consideration a hard reset
        for the ROM whenever a bitstream reload is demanded of the FPGA.

        The SpiOpi architecture is split into two levels: a command manager, and a cycle manager. The
        command manager is responsible for taking the current wishbone request and CSR state and
        unpacking these into cycle-by-cycle requests. The cycle manager is responsible for coordinating
        the cycle-by-cycle requests.

        In SPI mode, this means marshalling byte-wide requests into a series of 8 serial cyles.

        In OPI [DOPI] mode, this means marshalling 16-bit wide requests into a pair of back-to-back
        DDR cycles. Note that because the cycles are DDR, this means one 16-bit wide request must be
        issued every cycle to keep up with the interface.

        For the output of data to ROM, expects a clock called "spinor_delayed" which is a delayed
        version of "sys". The delay is necessary to get the correct phase relationship between the
        SIO and SCLK in DTR/DDR mode, and it also has to compensate for the special-case difference
        in the CCLK pad vs other I/O.

        For the input, DQS signal is independently delayed relative to the DQ signals using an IDELAYE2
        block. At a REFCLK frequency of 200 MHz, each delay tap adds 78ps, so up to a 2.418ns delay is
        possible between DQS and DQ. The goal is to delay DQS relative to DQ, because the SPI chip
        launches both with concurrent rising edges (to within 0.6ns), but the IDDR register needs the
        rising edge of DQS to be centered inside the DQ eye.

        In DOPI mode, there is a prefetch buffer. It will read `prefetch_lines` cache lines of data
        into the prefetch buffer. A cache line is 256 bits (or 8x32-bit words). The maximum value is
        63 lines (one line is necessary for synchronization margin). The downside of setting
        prefetch_lines high is that the prefetcher is running constantly and burning power, while
        throwing away most data. In practice, the CPU will typically consume data at only slightly
        faster than the rate of read-out from DOPI-mode ROM, and once data is consumed the prefetch
        resumes. Thus, prefetch_lines is probably optimally around 1-3 lines read-ahead of the CPU.
        Any higher than 3 lines probably just wastes power. In short simulations, 1 line of prefetch
        seems to be enough to keep the prefetcher ahead of the CPU even when it's simply running
        straight-line code.

        Note the "sim" parameter exists because there seems to be a bug in xvlog that doesn't
        correctly simulate the IDELAY machines. Setting "sim" to True removes the IDELAY machines
        and passes the data through directly, but in real hardware the IDELAY machines are necessary
        to meet timing between DQS and DQ.

        dq_delay_taps probably doesn't need to be adjusted; it can be tweaked for timing closure. The
        delays can also be adjusted at runtime.
        """)
        if prefetch_lines > 63:
            prefetch_lines = 63

        self.spi_mode = spi_mode = Signal(reset=1) # When reset is asserted, force into spi mode
        cs_n = Signal(reset=1) # Make sure CS is sane on reset, too

        self.config = CSRStorage(fields=[
            CSRField("dummy", size=5, description="Number of dummy cycles", reset=10),
        ])

        delay_type="VAR_LOAD"

        # DQS input conditioning -----------------------------------------------------------------
        dqs_iobuf = Signal()
        self.clock_domains.cd_dqs = ClockDomain(reset_less=True)
        self.comb += self.cd_dqs.clk.eq(dqs_iobuf)
        self.specials += [
            Instance("BUFR", i_I=pads.dqs, o_O=dqs_iobuf),
        ]

        # DQ connections -------------------------------------------------------------------------
        # PHY API
        self.do = Signal(16) # OPI data to SPI
        self.di = Signal(16) # OPI data from SPI
        self.tx = Signal()   # When asserted OPI is transmitting data to SPI, otherwise, receiving

        self.copi = Signal() # SPI data to SPI
        self.cipo = Signal() # SPI data from SPI

        # Delay programming API
        self.delay_config = CSRStorage(fields=[
            CSRField("d",    size=5, description="Delay amount; each increment is 78ps", reset=31),
            CSRField("load", size=1, description="Force delay taps to delay_d"),
        ])
        self.delay_status = CSRStatus(fields=[
            CSRField("q", size=5, description="Readback of current delay amount, useful if inc/ce is used to set"),
        ])
        self.delay_update  = Signal()
        self.hw_delay_load = Signal()
        self.sync += self.delay_update.eq(self.hw_delay_load | self.delay_config.fields.load)

        # Break system API into rising/falling edge samples
        do_rise = Signal(8) # data output presented on the rising edge
        do_fall = Signal(8) # data output presented on the falling edge
        self.comb += [do_rise.eq(self.do[8:]), do_fall.eq(self.do[:8])]

        di_rise = Signal(8)
        di_fall = Signal(8)
        self.comb += self.di.eq(Cat(di_fall, di_rise))

        # OPI DDR registers
        self.dq = dq = TSTriple(7) # dq[0] is special because it is also copi
        dq_delayed = Signal(8)
        self.specials += dq.get_tristate(pads.dq[1:])
        for i in range(1, 8):
            self.specials += Instance("ODDR",
                p_DDR_CLK_EDGE = "SAME_EDGE",
                i_C  = ClockSignal(),
                i_R  = ResetSignal(),
                i_S  = 0,
                i_CE = 1,
                i_D1 = do_rise[i],
                i_D2 = do_fall[i],
                o_Q  = dq.o[i-1],
            )
            if sim == False:
                if i == 1: # Only wire up o_CNTVALUEOUT for one instance
                    self.specials += Instance("IDELAYE2",
                        p_DELAY_SRC             = "IDATAIN",
                        p_SIGNAL_PATTERN        = "DATA",
                        p_CINVCTRL_SEL          = "FALSE",
                        p_HIGH_PERFORMANCE_MODE = "FALSE",
                        p_REFCLK_FREQUENCY      = 200.0,
                        p_PIPE_SEL              = "FALSE",
                        p_IDELAY_VALUE          = dq_delay_taps,
                        p_IDELAY_TYPE           = delay_type,

                        i_C           = ClockSignal(),
                        i_CINVCTRL    = 0,
                        i_REGRST      = 0,
                        i_LDPIPEEN    = 0,
                        i_INC         = 0,
                        i_CE          = 0,
                        i_LD          = self.delay_update,
                        i_CNTVALUEIN  = self.delay_config.fields.d,
                        o_CNTVALUEOUT = self.delay_status.fields.q,
                        i_IDATAIN     = dq.i[i-1],
                        o_DATAOUT     = dq_delayed[i],
                    ),
                else: # Don't wire up o_CNTVALUEOUT for others
                    self.specials += Instance("IDELAYE2",
                        p_DELAY_SRC             = "IDATAIN",
                        p_SIGNAL_PATTERN        = "DATA",
                        p_CINVCTRL_SEL          = "FALSE",
                        p_HIGH_PERFORMANCE_MODE = "FALSE",
                        p_REFCLK_FREQUENCY      = 200.0,
                        p_PIPE_SEL              = "FALSE",
                        p_IDELAY_VALUE          = dq_delay_taps,
                        p_IDELAY_TYPE           = delay_type,
                        i_C          = ClockSignal(),
                        i_CINVCTRL   = 0,
                        i_REGRST     = 0,
                        i_LDPIPEEN   = 0 ,
                        i_INC        = 0,
                        i_CE         = 0,
                        i_LD         = self.delay_update,
                        i_CNTVALUEIN = self.delay_config.fields.d,
                        i_IDATAIN    = dq.i[i-1],
                        o_DATAOUT    = dq_delayed[i],
                  ),
            else:
                self.comb += dq_delayed[i].eq(dq.i[i-1])
            self.specials += Instance("IDDR", name="{}{}".format(iddr_name, str(i)),
                p_DDR_CLK_EDGE = "SAME_EDGE_PIPELINED",
                i_C  = dqs_iobuf,
                i_R  = ResetSignal(),
                i_S  = 0,
                i_CE = 1,
                i_D  = dq_delayed[i],
                o_Q1 = di_rise[i],
                o_Q2 = di_fall[i],
            )
        # SPI SDR register
        self.specials += [
            Instance("FDRE", name="{}".format(cipo_name),
                i_C  = ~ClockSignal("spinor"),
                i_CE = 1,
                i_R  = 0,
                o_Q  = self.cipo,
                i_D  = dq_delayed[1],
            )
        ]

        # bit 0 (copi) is special-cased to handle SPI mode
        self.dq_copi = dq_copi = TSTriple(1) # this has similar structure but an independent "oe" signal
        self.specials += dq_copi.get_tristate(pads.dq[0])
        do_mux_rise = Signal() # mux signal for copi/dq select of bit 0
        do_mux_fall = Signal()
        self.specials += [
            Instance("ODDR",
                p_DDR_CLK_EDGE = "SAME_EDGE",
                i_C  = ClockSignal(),
                i_R  = ResetSignal(),
                i_S  = 0,
                i_CE = 1,
                i_D1 = do_mux_rise,
                i_D2 = do_mux_fall,
                o_Q  = dq_copi.o,
            ),
            Instance("IDDR",
                p_DDR_CLK_EDGE="SAME_EDGE_PIPELINED",
                i_C  = dqs_iobuf,
                i_R  = ResetSignal(),
                i_S  = 0,
                i_CE = 1,
                o_Q1 = di_rise[0],
                o_Q2 = di_fall[0],
                i_D  = dq_delayed[0],
            ),
        ]
        if sim == False:
            self.specials += Instance("IDELAYE2",
                p_DELAY_SRC             = "IDATAIN",
                p_SIGNAL_PATTERN        = "DATA",
                p_CINVCTRL_SEL          = "FALSE",
                p_HIGH_PERFORMANCE_MODE = "FALSE",
                p_REFCLK_FREQUENCY      = 200.0,
                p_PIPE_SEL              = "FALSE",
                p_IDELAY_VALUE          = dq_delay_taps,
                p_IDELAY_TYPE           = delay_type,

                i_C          = ClockSignal(),
                i_CINVCTRL   = 0,
                i_REGRST     = 0,
                i_LDPIPEEN   = 0,
                i_INC        = 0,
                i_CE         = 0,
                i_LD         = self.delay_update,
                i_CNTVALUEIN = self.delay_config.fields.d,
                i_IDATAIN    = dq_copi.i,
                o_DATAOUT    = dq_delayed[0],
            ),
        else:
            self.comb += dq_delayed[0].eq(dq_copi.i)

        # Wire up SCLK interface
        clk_en = Signal()
        self.specials += [
            # De-activate the CCLK interface, parallel it with a GPIO
            Instance("STARTUPE2",
                i_CLK       = 0,
                i_GSR       = 0,
                i_GTS       = 0,
                i_KEYCLEARB = 0,
                i_PACK      = 0,
                i_USRDONEO  = 1,
                i_USRDONETS = 1,
                i_USRCCLKO  = 0,
                i_USRCCLKTS = 1,  # Force to tristate
            ),
            Instance("ODDR", name=sclk_name, # Need to name this so we can constrain it properly
                p_DDR_CLK_EDGE = "SAME_EDGE",
                i_C  = ClockSignal("spinor"),
                i_R  = ResetSignal("spinor"),
                i_S  = 0,
                i_CE = 1,
                i_D1 = clk_en,
                i_D2 = 0,
                o_Q  = pads.sclk,
            )
        ]

        # wire up CS_N
        spi_cs_n = Signal()
        opi_cs_n = Signal()
        self.comb += cs_n.eq( (spi_mode & spi_cs_n) | (~spi_mode & opi_cs_n) )
        self.specials += [
            Instance("ODDR",
              p_DDR_CLK_EDGE="SAME_EDGE",
              i_C=ClockSignal(), i_R=0, i_S=ResetSignal(), i_CE=1,
              i_D1=cs_n, i_D2=cs_n, o_Q=pads.cs_n,
            ),
        ]

        self.architecture = ModuleDoc("""Architecture

        The machine is split into two separate pieces, one to handle SPI, and one to handle OPI.

        SPI
        -----

        The SPI machine architecture is split into two levels: MAC and PHY.

        The MAC layer is responsible for:
        - receiving requests via CSR register to perform config/status/special command sequences,
        and dispatching these to the SPI PHY
        - translating wishbone bus requests into command sequences, and routing them to either OPI
        or SPI PHY.
        - managing the chip select to the chip, and ensuring that one dummy cycle is inserted after
        chip select is asserted, or before it is de-asserted; and that the chip select "high" times
        are adequate (1 cycle between reads, 4 cycles for all other operations)

        On boot, the interface runs in SPI; once the wakeup sequence is executed, the chip permanently
        switches to OPI mode unless the CR2 registers are written to fall back, or the
        reset to the chip is asserted.

        The PHY layers are responsible for the following tasks:
        - Serializing and deserializing data, standardized on 8 bits for SPI and 16 bits for OPI
        - counting dummy cycles
        - managing the clock enable

        PHY cycles are initiated with a "req" signal, which is only sampled for
        one cycle and then ignored until the PHY issues an "ack" that the current cycle is complete.
        Thus holding "req" high can allow the PHY to back-to-back issue cycles without pause.

        OPI
        -----

        The OPI machine is split into three parts: a command controller, a Tx PHY, and an Rx PHY.

        The Tx PHY is configured with a "dummy cycle" count register, as there is a variable length
        delay for dummy cycles in OPI.

        In OPI mode, read data is `mesochronous`, that is, they return at precisely the same frequency
        as SCLK, but with an unknown phase relationship. The DQS strobe is provided as a "hint" to
        the receiving side to help retime the data. The mesochronous nature of the read data is why
        the Tx and Rx PHY must be split into two separate machines, as they are operating in
        different clock domains.

        DQS is implemented on the ROM as an extra data output that is guaranteed to change polarity
        with each data byte; the skew mismatch of DQS to data is within +/-0.6ns or so. It turns out
        the mere act of routing the DQS into a BUFR buffer before clocking the data into an IDDR
        primitive is sufficient to delay the DQS signal and meet setup and hold time on the IDDR.

        Once captured by the IDDR, the data is fed into a dual-clock FIFO to make the transition
        from the DQS to sysclk domains cleanly.

        Because of the latency involved in going from pin->IDDR->FIFO, excess read cycles are
        required beyond the end of the requested cache line. However, there is virtually no penalty
        in pre-filling the FIFO with data; if a new cache line has to be fetched, the FIFO can simply
        be reset and all pointers zeroed. In fact, pre-filling the FIFO can lead to great performance
        benefits if sequential cache lines are requested. In simulation, a cache line can be filled
        in 10 bus cycles if it happens to be prefetched (as opposed to 49 bus cycles for random reads).
        Either way, this compares favorably to 288 cycles for random reads in 100MHz SPI mode (or 576
        for the spimemio.v, which runs at 50MHz).

        The command controller is repsonsible for sequencing all commands other than fast reads. Most
        commands have some special-case structure to them, and as more commands are implemented, the
        state machine is expected to grow fairly large. Fast reads are directly handled in "tx_run"
        mode, where the TxPhy and RxPhy run a tight loop to watch incoming read bus cycles, check
        the current address, fill the prefetch fifo, and respond to bus cycles.

        Writes to ROM might lock up the machine; a TODO is to test this and do something more sane,
        like ignore writes by sending an ACK immediately while discarding the data.

        Thus, an OPI read proceeds as follows:

        - When BUS/STB are asserted:
           TxPhy:

           - capture bus_adr, and compare against the *next read* address pointer
              - if they match, allow the PHYs to do the work

           - if bus_adr and next read address don't match, save to next read address pointer, and
             cycle wr/rd clk for 5 cycle while asserting reset to reset the FIFO
           - initiate an 8DTRD with the read address pointer
           - wait the specified dummy cycles

           - greedily pre-fill the FIFO by continuing to clock DQS until either:
             - the FIFO is full
             - pre-fetch is aborted because bus_adr and next read address don't match and FIFO is reset

           RxPHY:

           - while CTI==2, assemble data into 32-bit words as soon as EMPTY is deasserted,
             present a bus_ack, and increment the next read address pointer
           - when CTI==7, ack the data, and wait until the next bus cycle with CTI==2 to resume
             reading

        - A FIFO_SYNC_MACRO is used to instantiate the FIFO. This is chosen because:
           - we can specify RAMB18's, which seem to be under-utilized by the auto-inferred memories by migen
           - the XPM_FIFO_ASYNC macro claims no instantiation support, and also looks like it has weird
             requirements for resetting the pointers: you must check the reset outputs, and the time to
             reset is reported to be as high as around 200ns (anecdotally -- could be just that the sim I
             read on the web is using a really slow clock, but I'm guessing it's around 10 cycles).
           - the FIFO_SYNC_MACRO has a well-specified fixed reset latency of 5 cycles.
           - The main downside of FIFO_SYNC_MACRO over XPM_FIFO_ASYNC is that XPM_FIFO_ASYNC can automatically
             allow for output data to be read at 32-bit widths, with writes at 16-bit widths. However, with a
             bit of additional logic and pipelining, we can aggregate data into 32-bit words going into a
             32-bit FIFO_SYNC_MACRO, which is what we do in this implementation.
        """)
        self.bus = bus = wishbone.Interface()

        self.command = CSRStorage(description="Write individual bits to issue special commands to SPI; setting multiple bits at once leads to undefined behavior.",
            fields=[
                CSRField("wakeup",       size=1, description="Sequence through init & wakeup routine"),
                CSRField("sector_erase", size=1, description="Erase a sector"),
            ])
        self.sector = CSRStorage(description="Sector to erase",
            fields=[
                CSRField("sector", size=32, description="Sector to erase")
            ])
        self.status = CSRStatus(description="Interface status",
            fields=[
                CSRField("wip", size=1, description="Operation in progress (write or erease)")
            ])
        # TODO: implement ECC detailed register readback, CRC checking

        # PHY machine mux --------------------------------------------------------------------------
        # clk_en mux
        spi_clk_en = Signal()
        opi_clk_en = Signal()
        self.sync += clk_en.eq(~spi_mode & opi_clk_en | spi_mode & spi_clk_en)
        # Tristate mux
        self.sync += [
            dq.oe.eq(~spi_mode & self.tx),
            dq_copi.oe.eq(spi_mode | self.tx),
        ]
        # Data out mux (no data in mux, as we can just sample data in all the time without harm)
        self.comb += do_mux_rise.eq(~spi_mode & do_rise[0] | spi_mode & self.copi)
        self.comb += do_mux_fall.eq(~spi_mode & do_fall[0] | spi_mode & self.copi)

        # Indicates if the current "req" requires dummy cycles to be appended (used for both OPI/SPI)
        has_dummy = Signal()
        # Location of the internal ROM address pointer; reset to invalid address to force an address
        # request on first read
        rom_addr  = Signal(32, reset=0xFFFFFFFC)

        # MAC/PHY abstraction for OPI
        txphy_do = Signal(16) # Two sources of data out for OPI, one from the PHY, one from MAC
        txcmd_do = Signal(16)
        opi_di   = Signal(16)

        # Internal machines
        opi_addr         = Signal(32)
        opi_fifo_rd      = Signal(32)
        opi_fifo_wd      = Signal(32)
        opi_reset_rx_req = Signal()
        opi_reset_rx_ack = Signal()
        opi_rx_run       = Signal()

        rx_almostempty = Signal()
        rx_almostfull  = Signal()
        rx_empty       = Signal()
        rx_full        = Signal()
        rx_rdcount     = Signal(9)
        rx_rderr       = Signal()
        rx_wrcount     = Signal(9)
        rx_wrerr       = Signal()
        rx_rden        = Signal()
        rx_wren        = Signal(reset=1)
        rx_fifo_rst    = Signal()

        wrendiv  = Signal()
        wrendiv2 = Signal()
        rx_fifo_rst_pipe = Signal()
        self.specials += [
            # This next pair of async-clear flip flops creates a write-enable gate that (a) ignores
            # the first two DQS strobes (as they are pipe-filling) and (b) alternates with the correct
            # phase so we are sampling 32-bit data into the FIFO.
            Instance("FDCE", name="FDCE_WREN",
                i_C   = dqs_iobuf,
                i_D   = ~wrendiv,
                o_Q   = wrendiv,
                i_CE  = 1,
                i_CLR = ~rx_wren,
            ),
            Instance("FDCE", name="FDCE_WREN",
                i_C   = dqs_iobuf,
                i_D   = ~wrendiv2,
                o_Q   = wrendiv2,
                i_CE  = wrendiv & ~wrendiv2,
                i_CLR = ~rx_wren,
            ),
            # Direct FIFO primitive is more resource-efficient and faster than migen primitive.
            Instance("FIFO_DUALCLOCK_MACRO",
                p_DEVICE                  = "7SERIES",
                p_FIFO_SIZE               = "18Kb",
                p_DATA_WIDTH              = 32,
                p_FIRST_WORD_FALL_THROUGH = "TRUE",
                p_ALMOST_EMPTY_OFFSET     = 6,
                p_ALMOST_FULL_OFFSET      = (511 - (8*prefetch_lines)),

                o_ALMOSTEMPTY = rx_almostempty,
                o_ALMOSTFULL  = rx_almostfull,
                o_DO          = opi_fifo_rd,
                o_EMPTY       = rx_empty,
                o_FULL        = rx_full,
                o_RDCOUNT     = rx_rdcount,
                o_RDERR       = rx_rderr,
                o_WRCOUNT     = rx_wrcount,
                o_WRERR       = rx_wrerr,
                i_DI          = opi_fifo_wd,
                i_RDCLK       = ClockSignal(),
                i_RDEN        = rx_rden,
                i_WRCLK       = dqs_iobuf,
                i_WREN        = wrendiv & wrendiv2,
                i_RST         = rx_fifo_rst_pipe, #rx_fifo_rst,
            )
        ]
        self.sync.dqs += opi_di.eq(self.di)
        self.comb += opi_fifo_wd.eq(Cat(opi_di, self.di))
        self.sync += rx_fifo_rst_pipe.eq(rx_fifo_rst) # add one pipe register to help relax this timing path. It is critical so it must be timed, but one extra cycle is OK.

        #---------  OPI Rx Phy machine ------------------------------
        self.submodules.rxphy = rxphy = FSM(reset_state="IDLE")
        cti_pipe = Signal(3)
        rxphy_cnt = Signal(3)
        rxphy.act("IDLE",
            If(spi_mode,
                NextState("IDLE"),
            ).Else(
                NextValue(bus.ack, 0),
                If(opi_reset_rx_req,
                    NextState("WAIT_RESET"),
                    NextValue(rxphy_cnt, 6),
                    NextValue(rx_wren, 0),
                    NextValue(rx_fifo_rst, 1)
                ).Elif(opi_rx_run,
                    NextValue(rx_wren, 1),
                    If((bus.cyc & bus.stb & ~bus.we) & ((bus.cti == 2) |
                       ((bus.cti == 7) & ~bus.ack) ), # handle case of non-pipelined read, ack is late
                        If(~rx_empty,
                            NextValue(bus.dat_r, opi_fifo_rd),
                            rx_rden.eq(1),
                            NextValue(opi_addr, opi_addr + 4),
                            NextValue(bus.ack, 1)
                        )
                    )
                )
            )
        )
        rxphy.act("WAIT_RESET",
            NextValue(opi_addr, Cat(Signal(2), bus.adr)),
            NextValue(rxphy_cnt, rxphy_cnt - 1),
            If(rxphy_cnt == 0,
                NextValue(rx_fifo_rst, 0),
                opi_reset_rx_ack.eq(1),
                NextState("IDLE")
            )
        )


        # TxPHY machine: OPI -------------------------------------------------------------------------
        txphy_cnt   = Signal(4)
        tx_run      = Signal()
        txphy_cs_n  = Signal(reset=1)
        txcmd_cs_n  = Signal(reset=1)
        txphy_clken = Signal()
        txcmd_clken = Signal()
        txphy_oe    = Signal()
        txcmd_oe    = Signal()
        self.sync += opi_cs_n.eq( (tx_run & txphy_cs_n) | (~tx_run & txcmd_cs_n) )
        self.comb += If( tx_run, self.do.eq(txphy_do) ).Else( self.do.eq(txcmd_do) )
        self.comb += opi_clk_en.eq( (tx_run & txphy_clken) | (~tx_run & txcmd_clken) )
        self.comb += self.tx.eq( (tx_run & txphy_oe) | (~tx_run & txcmd_oe) )
        tx_almostfull = Signal()
        self.sync += tx_almostfull.eq(rx_almostfull) # sync the rx_almostfull signal into the local clock domain
        txphy_bus = Signal()
        self.sync += txphy_bus.eq(bus.cyc & bus.stb & ~bus.we & (bus.cti == 2))
        tx_resetcycle = Signal()

        self.submodules.txphy = txphy = FSM(reset_state="RESET")
        txphy.act("RESET",
            NextValue(opi_rx_run, 0),
            NextValue(txphy_oe, 0),
            NextValue(txphy_cs_n, 1),
            NextValue(txphy_clken, 0),
            # guarantee that the first state we go to out of reset is a four-cycle burst
            NextValue(txphy_cnt, 4),
            If(tx_run & ~spi_mode,
                NextState("TX_SETUP")
            )
        )
        txphy.act("TX_SETUP",
            NextValue(opi_rx_run, 0),
            NextValue(txphy_cnt, txphy_cnt - 1),
            If( txphy_cnt > 0,
                NextValue(txphy_cs_n, 1)
            ).Else(
                NextValue(txphy_cs_n, 0),
                NextValue(txphy_oe, 1),
                NextState("TX_CMD_CS_DELAY")
            )
        )
        txphy.act("TX_CMD_CS_DELAY",  # meet setup timing for CS-to-clock
            NextState("TX_CMD")
        )
        txphy.act("TX_CMD",
            NextValue(txphy_do, 0xEE11),
            NextValue(txphy_clken, 1),
            NextState("TX_ADRHI")
        )
        txphy.act("TX_ADRHI",
            NextValue(txphy_do, opi_addr[16:] & 0x07FF), # mask off unused bits
            NextState("TX_ADRLO")
        )
        txphy.act("TX_ADRLO",
                  NextValue(txphy_do, opi_addr[:16]),
                  NextValue(txphy_cnt, self.config.fields.dummy - 1),
                  NextState("TX_DUMMY")
        )
        txphy.act("TX_DUMMY",
            NextValue(txphy_oe, 0),
            NextValue(txphy_do, 0),
            NextValue(txphy_cnt, txphy_cnt - 1),
            If(txphy_cnt == 0,
                NextValue(opi_rx_run, 1),
                If(tx_resetcycle,
                    NextValue(txphy_clken, 1),
                    NextValue(opi_reset_rx_req, 1),
                    NextState("TX_RESET_RX"),
                ).Else(
                    NextState("TX_FILL"),
               )
            )
        )
        txphy.act("TX_FILL",
            If(tx_run,
                If(((~txphy_bus & (bus.cyc & bus.stb & ~bus.we & (bus.cti == 2))) &
                   (opi_addr[2:] != bus.adr)) | tx_resetcycle,
                    # Tt's a new bus cycle, and the requested address is not equal to the current
                    # read buffer address
                    NextValue(txphy_clken, 1),
                    NextValue(opi_reset_rx_req, 1),
                    NextState("TX_RESET_RX"),
               ).Else(
                    If(tx_almostfull & ~bus.ack,
                        NextValue(txphy_clken, 0)
                    ).Else(
                        NextValue(txphy_clken, 1)
                    )
               ),
               If(~(bus.cyc & bus.stb),
                    NextValue(opi_rx_run, 0),
               ).Else(
                    NextValue(opi_rx_run, 1),
               )
            ).Else(
                NextValue(txphy_clken, 0),
                NextState("RESET")
            )
        )
        txphy.act("TX_RESET_RX", # Keep clocking the RX until it acknowledges a reset
            NextValue(opi_rx_run, 0),
            NextValue(opi_reset_rx_req, 0),
            If(opi_reset_rx_ack,
                NextValue(txphy_clken, 0),
                NextValue(txphy_cnt, 0), # 1 cycle CS on back-to-back reads
                NextValue(txphy_cs_n, 1),
                NextState("TX_SETUP"),
            ).Else(
                NextValue(txphy_clken, 1),
            )
        )

        #---------  OPI CMD machine ------------------------------
        self.submodules.opicmd = opicmd = FSM(reset_state="RESET")
        opicmd.act("RESET",
            NextValue(txcmd_do, 0),
            NextValue(txcmd_oe, 0),
            NextValue(tx_run, 0),
            NextValue(txcmd_cs_n, 1),
            If(~spi_mode,
                NextState("IDLE")
            ).Else(
                NextState("RESET_CYCLE")
            ),
        )
        opicmd.act("RESET_CYCLE",
            NextValue(txcmd_cs_n, 0),
            If(opi_reset_rx_ack,
                NextValue(tx_run, 1),
                NextState("IDLE"),
            ).Else(
                NextValue(tx_run, 1),
                tx_resetcycle.eq(1)
            )
        )
        opicmd.act("IDLE",
            NextValue(txcmd_cs_n, 1),
            If(~spi_mode,  # This machine stays in idle once spi_mode is dropped
               ## The full form of this machine is as follows:
               # - First check if there is a CSR special command pending
               #   - if so, wait until the current bus cycle is done, then de-assert tx_run
               #   - then run the command
               # - Else wait until a bus cycle, and once it happens, put the system into run mode
               If(bus.cyc & bus.stb,
                    If(~bus.we & (bus.cti ==2),
                        NextState("TX_RUN")
                    ).Else(
                        # Handle other cases here, e.g. what do we do if we get a write? probably
                        # should just ACK it without doing anything so the CPU doesn't freeze...
                    )
               ).Elif(self.command.re,
                    NextState("DISPATCH_CMD"),
               )
            )
        )
        opicmd.act("TX_RUN",
            NextValue(tx_run, 1),
            If(self.command.re, # Respond to commands
                NextState("WAIT_DISPATCH")
            )
        )
        # Wait until the current cycle is done, then stop TX and dispatch command
        opicmd.act("WAIT_DISPATCH",
            If( ~(bus.cyc & bus.stb),
                NextValue(tx_run, 0),
                NextState("DISPATCH_CMD")
            )
        )
        opicmd.act("DISPATCH_CMD",
            If(self.command.fields.sector_erase,
                NextState("DO_SECTOR_ERASE")
            ).Else(
                NextState("IDLE")
            )
        )
        opicmd.act("DO_SECTOR_ERASE",
            # Placeholder
        )

        # MAC/PHY abstraction for the SPI machine
        spi_req = Signal()
        spi_ack = Signal()
        spi_do  = Signal(8) # this is the API to the machine
        spi_di  = Signal(8)

        # PHY machine: SPI -------------------------------------------------------------------------

        # internal signals are:
        # selection - spi_mode
        # OPI - self.do(16), self.di(16), self.tx
        # SPI - self.copi, self.cipo
        # cs_n - both
        # ecs_n - OPI
        # clk_en - both

        spicount     = Signal(5)
        spi_so       = Signal(8) # this internal to the machine
        spi_si       = Signal(8)
        spi_dummy    = Signal()
        spi_di_load  = Signal() # spi_do load is pipelined back one cycle using this mechanism
        spi_di_load2 = Signal()
        spi_ack_pipe = Signal()
        # Pipelining is required the cipo path is very slow (IOB->fabric FD), and a falling-edge
        # retiming reg is used to meet timing
        self.sync += [
            spi_di_load2.eq(spi_di_load),
            If(spi_di_load2, spi_di.eq(Cat(self.cipo, spi_si[:-1]))).Else(spi_di.eq(spi_di)),
            spi_ack.eq(spi_ack_pipe),
        ]
        self.comb += self.copi.eq(spi_so[7])
        self.sync += spi_si.eq(Cat(self.cipo, spi_si[:-1]))
        self.submodules.spiphy = spiphy = FSM(reset_state="RESET")
        spiphy.act("RESET",
            If(spi_req,
                NextState("REQ"),
                NextValue(spicount, 7),
                NextValue(spi_clk_en, 1),
                NextValue(spi_so, spi_do),
                NextValue(spi_dummy, has_dummy),
            ).Else(
                NextValue(spi_clk_en, 0),
                NextValue(spi_ack_pipe, 0),
                NextValue(spicount, 0),
                NextValue(spi_dummy, 0),
            )
        )
        spiphy.act("REQ",
            If(spicount > 0,
                NextValue(spicount, spicount-1),
                NextValue(spi_clk_en, 1),
                NextValue(spi_so, Cat(0, spi_so[:-1])),
                NextValue(spi_ack_pipe, 0)
            ).Elif( (spicount == 0) & spi_req & ~spi_dummy, # Back-to-back transaction
                NextValue(spi_clk_en, 1),
                NextValue(spicount, 7),
                NextValue(spi_clk_en, 1),
                NextValue(spi_so, spi_do), # Reload the so register
                spi_di_load.eq(1), # "naked" .eq() create single-cycle pulses that default back to 0
                NextValue(spi_ack_pipe, 1),
                NextValue(spi_dummy, has_dummy)
            ).Elif( (spicount == 0) & ~spi_req & ~spi_dummy, # Go back to idle
                spi_di_load.eq(1),
                NextValue(spi_ack_pipe, 1),
                NextValue(spi_clk_en, 0),
                NextState("RESET")
            ).Elif( (spicount == 0) & spi_dummy,
                spi_di_load.eq(1),
                NextValue(spicount, self.config.fields.dummy),
                NextValue(spi_clk_en, 1),
                NextValue(spi_ack_pipe, 0),
                NextValue(spi_so, 0),  # Do a dummy with '0' as the output
                NextState("DUMMY")
            ) # This actually should be a fully defined situation, no "Else" applicable
        )
        spiphy.act("DUMMY",
            If(spicount > 1, # Instead of doing dummy-1, we stop at count == 1
                NextValue(spicount, spicount - 1),
                NextValue(spi_clk_en, 1)
            ).Elif(spicount <= 1 & spi_req,
                NextValue(spi_clk_en, 1),
                NextValue(spicount, 7),
                NextValue(spi_so, spi_do),  # Reload the so register
                NextValue(spi_ack_pipe, 1), # Finally ack the cycle
                NextValue(spi_dummy, has_dummy)
            ).Else(
                NextValue(spi_clk_en, 0),
                NextValue(spi_ack_pipe, 1),  # Finally ack the cycle
                NextState("RESET")
            )
        )

        # SPI MAC machine --------------------------------------------------------------------------
        # default active on boot
        addr_updated = Signal()
        d_to_wb      = Signal(32) # data going back to wishbone
        mac_count    = Signal(5)
        new_cycle    = Signal(1)
        self.submodules.mac = mac = FSM(reset_state="RESET")
        mac.act("RESET",
                NextValue(spi_mode, 1),
                NextValue(addr_updated, 0),
                NextValue(d_to_wb, 0),
                NextValue(spi_cs_n, 1),
                NextValue(has_dummy, 0),
                NextValue(spi_do, 0),
                NextValue(spi_req, 0),
                NextValue(mac_count, 0),
                NextState("WAKEUP_PRE"),
                NextValue(new_cycle, 1),
                If(spi_mode, NextValue(bus.ack, 0)),
        )
        if spiread:
            mac.act("IDLE",
                If(spi_mode, # This machine stays in idle once spi_mode is dropped
                    NextValue(bus.ack, 0),
                    If((bus.cyc == 1) & (bus.stb == 1) & (bus.we == 0) & (bus.cti != 7), # read cycle requested, not end-of-burst
                        If( (rom_addr[2:] != bus.adr) & new_cycle,
                            NextValue(rom_addr, Cat(Signal(2, reset=0), bus.adr)),
                            NextValue(addr_updated, 1),
                            NextValue(spi_cs_n, 1), # raise CS in anticipation of a new address cycle
                            NextState("SPI_READ_32_CS"),
                        ).Elif( (rom_addr[2:] == bus.adr) | (~new_cycle & bus.cti == 2),
                            NextValue(mac_count, 3),  # get another beat of 4 bytes at the next address
                            NextState("SPI_READ_32")
                        ).Else(
                            NextValue(addr_updated, 0),
                            NextValue(spi_cs_n, 0),
                            NextState("SPI_READ_32"),
                            NextValue(mac_count, 3),  # prep the MAC state counter to count out 4 bytes
                        )
                    ).Elif(self.command.fields.wakeup,
                            NextValue(spi_cs_n, 1),
                            NextValue(self.command.storage, 0),  # clear all pending commands
                            NextState("WAKEUP_PRE"),
                    )
                )
            )
        else:
            mac.act("IDLE",
                If(spi_mode, # This machine stays in idle once spi_mode is dropped
                    If(self.command.fields.wakeup,
                        NextValue(spi_cs_n, 1),
                        NextValue(self.command.storage, 0),  # Clear all pending commands
                        NextState("WAKEUP_PRE"),
                    )
                )
            )

        #---------  wakup chip ------------------------------
        mac.act("WAKEUP_PRE",
            NextValue(spi_cs_n, 1), # Why isn't this sticking? i shouldn't have to put this here
            NextValue(mac_count, 4),
            NextState("WAKEUP_PRE_CS_WAIT")
        )
        mac.act("WAKEUP_PRE_CS_WAIT",
            NextValue(mac_count, mac_count-1),
            If(mac_count == 0,
               NextState("WAKEUP_WUP"),
               NextValue(spi_cs_n, 0)
            )
        )
        mac.act("WAKEUP_WUP",
            NextValue(mac_count, mac_count-1),
            If(mac_count == 0,
               NextValue(spi_cs_n, 0),
               NextValue(spi_do, 0xab),  # wakeup from deep sleep
               NextValue(spi_req, 1),
               NextState("WAKEUP_WUP_WAIT")
            )
        )
        mac.act("WAKEUP_WUP_WAIT",
            NextValue(spi_req, 0),
            If(spi_ack,
               NextValue(spi_cs_n, 1),   # raise CS
               NextValue(mac_count, 4),  # for >4 cycles per specsheet
               NextState("WAKEUP_CR2_WREN_1")
            )
        )

        #---------  WREN+CR2 - dummy cycles ------------------------------
        mac.act("WAKEUP_CR2_WREN_1",
            NextValue(mac_count, mac_count-1),
            If(mac_count == 0,
               NextValue(spi_cs_n, 0),
               NextValue(spi_do, 0x06),  # WREN to unlock CR2 writing
               NextValue(spi_req, 1),
               NextState("WAKEUP_CR2_WREN_1_WAIT")
            )
        )
        mac.act("WAKEUP_CR2_WREN_1_WAIT",
            NextValue(spi_req, 0),
            If(spi_ack,
               NextValue(spi_cs_n, 1),
               NextValue(mac_count, 4),
               NextState("WAKEUP_CR2_DUMMY_CMD")
            )
        )
        mac.act("WAKEUP_CR2_DUMMY_CMD",
            NextValue(mac_count, mac_count-1),
            If(mac_count == 0,
                NextValue(spi_cs_n, 0),
                NextValue(spi_do, 0x72), # CR2 command
                NextValue(spi_req, 1),
                NextValue(mac_count, 2),
                NextState("WAKEUP_CR2_DUMMY_ADRHI")
            )
        )
        mac.act("WAKEUP_CR2_DUMMY_ADRHI",
            NextValue(spi_do, 0x00), # We want to send 00_00_03_00
            If(spi_ack,
               NextValue(mac_count, mac_count -1)
            ),
            If(mac_count == 0,
               NextState("WAKEUP_CR2_DUMMY_ADRMID")
            )
        )
        mac.act("WAKEUP_CR2_DUMMY_ADRMID",
            NextValue(spi_do, 0x03),
            If(spi_ack,
                NextState("WAKEUP_CR2_DUMMY_ADRLO")
            )
        )
        mac.act("WAKEUP_CR2_DUMMY_ADRLO",
            NextValue(spi_do, 0x00),
            If(spi_ack,
                NextState("WAKEUP_CR2_DUMMY_DATA")
            )
        )
        mac.act("WAKEUP_CR2_DUMMY_DATA",
            NextValue(spi_do, 0x05), # 10 dummy cycles as required for 84MHz-104MHz operation
            If(spi_ack,
                NextState("WAKEUP_CR2_DUMMY_WAIT")
            ),
        )
        mac.act("WAKEUP_CR2_DUMMY_WAIT",
            NextValue(spi_req, 0),
            If(spi_ack,
                NextValue(spi_cs_n, 1),
                NextValue(mac_count, 4),
                NextState("WAKEUP_CR2_WREN_2")
            )
        )

        #---------  WREN+CR2 to DOPI mode ------------------------------
        mac.act("WAKEUP_CR2_WREN_2",
            NextValue(mac_count, mac_count-1),
            If(mac_count == 0,
                NextValue(spi_cs_n, 0),
                NextValue(spi_do, 0x06),  # WREN to unlock CR2 writing
                NextValue(spi_req, 1),
                NextState("WAKEUP_CR2_WREN_2_WAIT")
            )
        )
        mac.act("WAKEUP_CR2_WREN_2_WAIT",
            NextValue(spi_req, 0),
            If(spi_ack,
                NextValue(spi_cs_n, 1),
                NextValue(mac_count, 4),
                NextState("WAKEUP_CR2_DOPI_CMD")
            )
        )
        mac.act("WAKEUP_CR2_DOPI_CMD",
            NextValue(mac_count, mac_count-1),
            If(mac_count == 0,
                NextValue(spi_cs_n, 0),
                NextValue(spi_do, 0x72),  # CR2 command
                NextValue(spi_req, 1),
                NextValue(mac_count, 4),
                NextState("WAKEUP_CR2_DOPI_ADR")
            )
        )
        mac.act("WAKEUP_CR2_DOPI_ADR",  # send 0x00_00_00_00 as address
            NextValue(spi_do, 0x00),  # no need to raise CS or lower spi_req, this is back-to-back
            If(spi_ack,
               NextValue(mac_count, mac_count - 1)
            ),
            If(mac_count == 0,
               NextState("WAKEUP_CR2_DOPI_DATA")
            )
        ),
        mac.act("WAKEUP_CR2_DOPI_DATA",
            NextValue(spi_do, 2),    # enable DOPI mode
            If(spi_ack,
                NextState("WAKEUP_CR2_DOPI_WAIT")
            )
        )
        mac.act("WAKEUP_CR2_DOPI_WAIT", # trailing CS wait
            NextValue(spi_req, 0),
            If(spi_ack,
               NextValue(spi_cs_n, 1),
               NextValue(mac_count, 4),
               NextState("WAKEUP_CS_EXIT")
            )
        )
        mac.act("WAKEUP_CS_EXIT",
            NextValue(spi_mode, 0),  # now enter DOPI mode
            NextValue(mac_count, mac_count-1),
            If(mac_count == 0,
               NextState("IDLE")
            )
        )

        if spiread:
            #---------  SPI read machine ------------------------------
            mac.act("SPI_READ_32",
                If(addr_updated,
                    NextState("SPI_READ_32_CS"),
                    NextValue(has_dummy, 0),
                    NextValue(mac_count, 3),
                    NextValue(spi_cs_n, 1),
                    NextValue(spi_req, 0),
                ).Else(
                    If(mac_count > 0,
                        NextValue(has_dummy, 0),
                        NextValue(spi_req, 1),
                        NextState("SPI_READ_32_D")
                    ).Else(
                        NextValue(spi_req, 0),
                        If(spi_ack,
                            # Protect these in a spi_mode mux to prevent excess inference of logic to
                            # handle otherwise implicit dual-controller situation
                            If(spi_mode,
                                NextValue(bus.dat_r, Cat(d_to_wb[8:],spi_di)),
                                NextValue(bus.ack, 1),
                           ),
                           NextValue(rom_addr, rom_addr + 1),
                           NextState("IDLE")
                        )
                    )
                )
            )
            mac.act("SPI_READ_32_D",
                If(spi_ack,
                   # Shift in one byte at a time to d_to_wb(32)
                   NextValue(d_to_wb, Cat(d_to_wb[8:],spi_di,)),
                   NextValue(mac_count, mac_count - 1),
                   NextState("SPI_READ_32"),
                   NextValue(rom_addr, rom_addr + 1)
                )
            )
            mac.act("SPI_READ_32_CS",
                NextValue(mac_count, mac_count-1),
                If(mac_count == 0,
                   NextValue(spi_cs_n, 0),
                   NextState("SPI_READ_32_A0")
                )
            )
            mac.act("SPI_READ_32_A0",
                NextValue(spi_do, 0x0c), # 32-bit address write for "fast read" command
                NextValue(spi_req, 1),
                NextState("SPI_READ_32_A1")
            )
            mac.act("SPI_READ_32_A1",
                NextValue(spi_do, rom_addr[24:] & 0x7), # queue up MSB to send, leave req high; mask off unused high bits
                If(spi_ack,
                   NextState("SPI_READ_32_A2")
                )
            )
            mac.act("SPI_READ_32_A2",
                NextValue(spi_do, rom_addr[16:24]),
                If(spi_ack,
                   NextState("SPI_READ_32_A3")
                )
            )
            mac.act("SPI_READ_32_A3",
                NextValue(spi_do, rom_addr[8:16]),
                If(spi_ack,
                   NextState("SPI_READ_32_A4")
                )
            )
            mac.act("SPI_READ_32_A4",
                NextValue(spi_do, rom_addr[:8]),
                If(spi_ack,
                   NextState("SPI_READ_32_A5")
                )
            )
            mac.act("SPI_READ_32_A5",
                NextValue(spi_do, 0),
                If(spi_ack,
                   NextState("SPI_READ_32_DUMMY")
                )
            )
            mac.act("SPI_READ_32_DUMMY",
                NextValue(spi_req, 0),
                NextValue(addr_updated, 0),
                If(spi_ack,
                   NextState("SPI_READ_32"),
                   NextValue(mac_count, 3),  # Prep the MAC state counter to count out 4 bytes
                ).Else(
                    NextState("SPI_READ_32_DUMMY")
                )
            )

        # Handle ECS_n -----------------------------------------------------------------------------
        # treat ECS_N as an async signal -- just a "rough guide" of problems
        ecs_n = Signal()
        self.specials += MultiReg(pads.ecs_n, ecs_n)

        self.submodules.ev = EventManager()
        self.ev.ecc_error = EventSourceProcess(description="An ECC event has happened on the current block; triggered by falling edge of ECC_N")
        self.ev.finalize()
        self.comb += self.ev.ecc_error.trigger.eq(ecs_n)
        ecc_reported = Signal()
        ecs_n_delay  = Signal()
        ecs_pulse    = Signal()

        self.ecc_address = CSRStatus(fields=[
            CSRField("ecc_address", size=32, description="Address of the most recent ECC event")
        ])
        self.ecc_status = CSRStatus(fields=[
            CSRField("ecc_error",    size=1, description="Live status of the ECS_N bit (ECC error on current packet when low)"),
            CSRField("ecc_overflow", size=1, description="More than one ECS_N event has happened since th last time ecc_address was checked")
        ])

        self.comb += self.ecc_status.fields.ecc_error.eq(ecs_n)
        self.comb += [
            ecs_pulse.eq(ecs_n_delay & ~ecs_n), # falling edge -> positive pulse
            If(ecs_pulse,
               self.ecc_address.fields.ecc_address.eq(rom_addr),
               If(ecc_reported,
                  self.ecc_status.fields.ecc_overflow.eq(1)
               ).Else(
                   self.ecc_status.fields.ecc_overflow.eq(self.ecc_status.fields.ecc_overflow),
               )
            ).Else(
                self.ecc_address.fields.ecc_address.eq(self.ecc_address.fields.ecc_address),
                If(self.ecc_status.we,
                   self.ecc_status.fields.ecc_overflow.eq(0),
                ).Else(
                    self.ecc_status.fields.ecc_overflow.eq(self.ecc_status.fields.ecc_overflow),
                )
            )
        ]
        self.sync += [
            ecs_n_delay.eq(ecs_n),
            If(ecs_pulse,
               ecc_reported.eq(1)
            ).Elif(self.ecc_address.we,
                ecc_reported.eq(0)
            )
        ]
