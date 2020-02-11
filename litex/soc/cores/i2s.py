# This file is Copyright (c) 2020 bunnie <bunnie@kosagi.com>
# License: BSD

from migen.genlib.cdc import MultiReg

from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr_eventmanager import *

from litex.soc.integration.doc import AutoDoc, ModuleDoc


class S7I2SSlave(Module, AutoCSR, AutoDoc):
    def __init__(self, pads, fifo_depth=256):
        self.intro = ModuleDoc("""
        Intro
        *******

        I2S slave creates a slave audio interface instance. Tx and Rx interfaces are inferred based
        upon the presence or absence of the respective pins in the "pads" argument.

        The interface is I2S-like, but note the deviation that the bits are justified left without a
        1-bit pad after sync edges. This isn't a problem for talking to the LM49352 codec this was
        designed for, as the bit offset is programmable, but this will not work well if are talking
        to a CODEC without a programmable bit offset!

        System Interface
        =================

        Audio interchange is done with the system using 16-bit stereo samples, with the right channel
        mapped to the least significant word of a 32-bit word. Thus each 32-bit word is a single
        stereo sample. As this is a slave I2S interface, sampling rate and framing is set by the
        programming of the audio CODEC chip. A slave situation is preferred because this defers the
        generation of audio clocks to the CODEC, which has PLLs specialized to generate the correct
        frequencies for audio sampling rates.

        `fifo_depth` is the depth at which either a read interrupt is fired (guaranteeing at least
        `fifo_depth` stereo samples in the receive FIFO) or a write interrupt is fired (guaranteeing
        at least `fifo_depth` free space in the transmit FIFO). The maximum depth is 512.

        To receive audio data:

        - reset the Rx FIFO, to guarantee all pointers at zero
        - hook the Rx full interrupt with an interrupt handler (optional)
        - if the CODEC is not yet transmitting data, initiate data transmission
        - enable Rx FIFO to run
        - poll or wait for interrupt; upon interrupt, read `fifo_depth` words. Repeat.
        - to close the stream, simply clear the Rx FIFO enable bit. The next initiation should call a
          reset of the FIFO to ensure leftover previous data is cleared from the FIFO.

        To transmit audio data:

        - reset the Tx FIFO, to guarantee all pointers at zero
        - hook the Tx available interrupt with an interrupt handler (optional)
        - write 512 words of data into the Tx FIFO, filling it to the max
        - if the CODEC is not yet requesting data and unmuted, unmute and initiate reception
        - enable the Tx FIFO to run
        - poll or wait for interrupt; upon interrupt, write `fifo_depth` words. Repeat.
        - to close stream, mute the DAC and stop the request clock. Ideally, this can be completed
        before the FIFO is emptied, so there is no jarring pop or truncation of data
        - stop FIFO running. Next initiation should reset the FIFO to ensure leftover previous data
        in FIFO is cleared.

        CODEC Interface
        ================

        The interface assumes we have a sysclk domain running around 100MHz, and that our typical max
        audio rate is 44.1kHz * 24bits * 2channels = 2.1168MHz audio clock. Thus, the architecture
        treats the audio clock and data as asynchronous inputs that are MultiReg-syncd into the clock
        domain. Probably the slowest sysclk rate this might work with is around 20-25MHz (10x over
        sampling), but at 100MHz things will be quite comfortable.

        The upside of the fully asynchronous implementation is that we can leave the I/O unconstrained,
        giving the place/route more latitude to do its job.

        Here's the timing format targeted by this I2S interface:

            .. wavedrom::
                :caption: Timing format of the I2S interface

                { "signal" : [
                  { "name": "clk",         "wave": "n....|.......|......" },
                  { "name": "sync",        "wave": "1.0..|....1..|....0." },
                  { "name": "tx/rx",       "wave": ".====|==x.===|==x.=x", "data":
                  ["L15", "L14", "...", "L1", "L0", "R15", "R14", "...", "R1", "R0", "L15"] },
                ]}

        - Data is updated on the falling edge
        - Data is sampled on the rising edge
        - Words are MSB-to-LSB, left-justified (**NOTE: this is a deviation from strict I2S, which
        offsets by 1 from the left**)
        - Sync is an input (FPGA is slave, codec is master): low => left channel, high => right channel
        - Sync can be longer than the wordlen, extra bits are just ignored
        - Tx is data to the codec (SDI pin on LM49352)
        - Rx is data from the codec (SDO pin on LM49352)

        """)

        # One cache line is 8 32-bit words, need to always have enough space for one line or else
        # nothing works
        if fifo_depth > 504:
            fifo_depth = 504
            print("I2S warning: fifo depth greater than 504 selected; truncating to 504")
        if fifo_depth < 8:
            fifo_depth = 8
            print("I2S warning: fifo depth less than 8 selected; truncating to 8")

        # Connect pins, synchronizers, and edge detectors
        if hasattr(pads, 'tx'):
            tx_pin = Signal()
            self.comb += pads.tx.eq(tx_pin)
        if hasattr(pads, 'rx'):
            rx_pin = Signal()
            self.specials += MultiReg(pads.rx, rx_pin)
        sync_pin = Signal()
        self.specials += MultiReg(pads.sync, sync_pin)

        clk_pin = Signal()
        self.specials += MultiReg(pads.clk, clk_pin)
        clk_d = Signal()
        self.sync += clk_d.eq(clk_pin)
        rising_edge  = Signal()
        falling_edge = Signal()
        self.comb += [rising_edge.eq(clk_pin & ~clk_d), falling_edge.eq(~clk_pin & clk_d)]

        # Wishbone bus
        self.bus = bus = wishbone.Interface()
        rd_ack = Signal()
        wr_ack = Signal()
        self.comb +=[
            If(bus.we,
               bus.ack.eq(wr_ack),
            ).Else(
                bus.ack.eq(rd_ack),
            )
        ]

        # Interrupts
        self.submodules.ev = EventManager()
        if hasattr(pads, 'rx'):
            self.ev.rx_ready = EventSourcePulse(description="Indicates FIFO is ready to read")  # Rising edge triggered
            self.ev.rx_error = EventSourcePulse(description="Indicates an Rx error has happened (over/underflow)")
        if hasattr(pads, 'tx'):
            self.ev.tx_ready = EventSourcePulse(description="Indicates enough space available for next Tx quanta of {} words".format(fifo_depth))
            self.ev.tx_error = EventSourcePulse(description="Indicates a Tx error has happened (over/underflow")
        self.ev.finalize()


        # build the RX subsystem
        if hasattr(pads, 'rx'):
            rx_rd_d        = Signal(32)
            rx_almostfull  = Signal()
            rx_almostempty = Signal()
            rx_full        = Signal()
            rx_empty       = Signal()
            rx_rdcount     = Signal(9)
            rx_rderr       = Signal()
            rx_wrerr       = Signal()
            rx_wrcount     = Signal(9)
            rx_rden        = Signal()
            rx_wr_d        = Signal(32)
            rx_wren        = Signal()

            self.rx_ctl = CSRStorage(description="Rx data path control",
                fields=[
                    CSRField("enable", size=1, description="Enable the receiving data"),
                    CSRField("reset",  size=1, description="Writing `1` resets the FIFO. Reset happens regardless of enable state.", pulse=1)
                ])
            self.rx_stat = CSRStatus(description="Rx data path status",
                fields=[
                    CSRField("overflow",  size=1, description="Rx overflow"),
                    CSRField("underflow", size=1, description="Rx underflow"),
                    CSRField("dataready", size=1, description="{} words of data loaded and ready to read".format(fifo_depth)),
                    CSRField("empty",     size=1, description="No data available in FIFO to read"), # next flags probably never used
                    CSRField("wrcount",   size=9, description="Write count"),
                    CSRField("rdcount",   size=9, description="Read count"),
                    CSRField("fifo_depth", size=9, description="FIFO depth as synthesized")
                ])
            self.comb += self.rx_stat.fields.fifo_depth.eq(fifo_depth)

            rx_rst_cnt = Signal(3)
            rx_reset   = Signal()
            self.sync += [
                If(self.rx_ctl.fields.reset,
                   rx_rst_cnt.eq(5),  # 5 cycles reset required by design
                   rx_reset.eq(1)
                ).Else(
                    If(rx_rst_cnt == 0,
                       rx_reset.eq(0)
                    ).Else(
                        rx_rst_cnt.eq(rx_rst_cnt - 1),
                        rx_reset.eq(1)
                    )
                )
            ]
            # At a width of 32 bits, an 18kiB fifo is 512 entries deep
            self.specials += Instance("FIFO_SYNC_MACRO",
                p_DEVICE              = "7SERIES",
                p_FIFO_SIZE           = "18Kb",
                p_DATA_WIDTH          = 32,
                p_ALMOST_EMPTY_OFFSET = 8,
                p_ALMOST_FULL_OFFSET  = (512 - fifo_depth),
                p_DO_REG              = 0,
                i_CLK         = ClockSignal(),
                i_RST         = rx_reset,
                o_ALMOSTFULL  = rx_almostfull,
                o_ALMOSTEMPTY = rx_almostempty,
                o_FULL        = rx_full,
                o_EMPTY       = rx_empty,
                i_WREN        = rx_wren & ~rx_reset,
                i_DI          = rx_wr_d,
                i_RDEN        = rx_rden & ~rx_reset,
                o_DO          = rx_rd_d,
                o_RDCOUNT     = rx_rdcount,
                o_RDERR       = rx_rderr,
                o_WRCOUNT     = rx_wrcount,
                o_WRERR       = rx_wrerr,
            )
            self.comb += [  # Wire up the status signals and interrupts
                self.rx_stat.fields.overflow.eq(rx_wrerr),
                self.rx_stat.fields.underflow.eq(rx_rderr),
                self.rx_stat.fields.dataready.eq(rx_almostfull),
                self.rx_stat.fields.wrcount.eq(rx_wrcount),
                self.rx_stat.fields.rdcount.eq(rx_rdcount),
                self.ev.rx_ready.trigger.eq(rx_almostfull),
                self.ev.rx_error.trigger.eq(rx_wrerr | rx_rderr),
            ]
            bus_read    = Signal()
            bus_read_d  = Signal()
            rd_ack_pipe = Signal()
            self.comb += bus_read.eq(bus.cyc & bus.stb & ~bus.we & (bus.cti == 0))
            self.sync += [  # This is the bus responder -- only works for uncached memory regions
                bus_read_d.eq(bus_read),
                If(bus_read & ~bus_read_d, # One response, one cycle
                   rd_ack_pipe.eq(1),
                   If(~rx_empty,
                      bus.dat_r.eq(rx_rd_d),
                      rx_rden.eq(1),
                   ).Else(
                       # Don't stall the bus indefinitely if we try to read from an empty fifo...just
                       # return garbage
                       bus.dat_r.eq(0xdeadbeef),
                       rx_rden.eq(0),
                   )
                ).Else(
                    rx_rden.eq(0),
                    rd_ack_pipe.eq(0),
                ),
                rd_ack.eq(rd_ack_pipe),
            ]

            rx_cnt = Signal(5)
            self.submodules.rxi2s = rxi2s = FSM(reset_state="IDLE")
            rxi2s.act("IDLE",
                NextValue(rx_wr_d, 0),
                If(self.rx_ctl.fields.enable,
                    # Wait_sync guarantees we start at the beginning of a left frame, and not in
                    # the middle
                    If(rising_edge & sync_pin,
                        NextState("WAIT_SYNC")
                   )
                )
            ),
            rxi2s.act("WAIT_SYNC",
                If(rising_edge & ~sync_pin,
                    NextState("LEFT"),
                    NextValue(rx_cnt, 16)
                ),
            )
            rxi2s.act("LEFT",
                If(~self.rx_ctl.fields.enable,
                    NextState("IDLE")
                ).Else(
                    NextValue(rx_wr_d, Cat(rx_pin, rx_wr_d[:-1])),
                    NextValue(rx_cnt, rx_cnt - 1),
                    NextState("LEFT_WAIT")
                )
            )
            rxi2s.act("LEFT_WAIT",
                If(~self.rx_ctl.fields.enable,
                    NextState("IDLE")
                ).Else(
                    If(rising_edge,
                        If((rx_cnt == 0) & sync_pin,
                            NextValue(rx_cnt, 16),
                            NextState("RIGHT")
                        ).Elif(rx_cnt > 0,
                            NextState("LEFT")
                        )
                    )
                )
            )
            rxi2s.act("RIGHT",
                If(~self.rx_ctl.fields.enable,
                    NextState("IDLE")
                ).Else(
                    NextValue(rx_wr_d, Cat(rx_pin, rx_wr_d[:-1])),
                    NextValue(rx_cnt, rx_cnt - 1),
                    NextState("RIGHT_WAIT")
                )
            )
            rxi2s.act("RIGHT_WAIT",
                If(~self.rx_ctl.fields.enable,
                    NextState("IDLE")
                ).Else(
                    If(rising_edge,
                        If((rx_cnt == 0) & ~sync_pin,
                            NextValue(rx_cnt, 16),
                            NextState("LEFT"),
                            rx_wren.eq(1) # Pulse rx_wren to write the current data word
                        ).Elif(rx_cnt > 0,
                            NextState("RIGHT")
                        )
                    )
                )
            )


        # Build the TX subsystem
        if hasattr(pads, 'tx'):
            tx_rd_d        = Signal(32)
            tx_almostfull  = Signal()
            tx_almostempty = Signal()
            tx_full        = Signal()
            tx_empty       = Signal()
            tx_rdcount     = Signal(9)
            tx_rderr       = Signal()
            tx_wrerr       = Signal()
            tx_wrcount     = Signal(9)
            tx_rden        = Signal()
            tx_wr_d        = Signal(32)
            tx_wren        = Signal()

            self.tx_ctl = CSRStorage(description="Tx data path control",
                fields=[
                    CSRField("enable", size=1, description="Enable the transmission data"),
                    CSRField("reset",  size=1, description="Writing `1` resets the FIFO. Reset happens regardless of enable state.", pulse=1)
                ])
            self.tx_stat = CSRStatus(description="Tx data path status",
                fields=[
                    CSRField("overflow",   size=1, description="Tx overflow"),
                    CSRField("underflow",  size=1, description="Tx underflow"),
                    CSRField("free",       size=1, description="At least {} words of space free".format(fifo_depth)),
                    CSRField("almostfull", size=1, description="Less than 8 words space available"), # the next few flags should be rarely used
                    CSRField("full",       size=1, description="FIFO is full or overfull"),
                    CSRField("empty",      size=1, description="FIFO is empty"),
                    CSRField("wrcount",    size=9, description="Tx write count"),
                    CSRField("rdcount",    size=9, description="Tx read count"),
                ])

            tx_rst_cnt = Signal(3)
            tx_reset   = Signal()
            self.sync += [
                If(self.tx_ctl.fields.reset,
                   tx_rst_cnt.eq(5), # 5 cycles reset required by design
                   tx_reset.eq(1)
                ).Else(
                    If(tx_rst_cnt == 0,
                       tx_reset.eq(0)
                    ).Else(
                        tx_rst_cnt.eq(tx_rst_cnt - 1),
                        tx_reset.eq(1)
                    )
                )
            ]
            # At a width of 32 bits, an 18kiB fifo is 512 entries deep
            self.specials += Instance("FIFO_SYNC_MACRO",
                p_DEVICE              = "7SERIES",
                p_FIFO_SIZE           = "18Kb",
                p_DATA_WIDTH          = 32,
                p_ALMOST_EMPTY_OFFSET = fifo_depth,
                p_ALMOST_FULL_OFFSET  = 8,
                p_DO_REG              = 0,
                i_CLK         = ClockSignal(),
                i_RST         = tx_reset,
                o_ALMOSTFULL  = tx_almostfull,
                o_ALMOSTEMPTY = tx_almostempty,
                o_FULL        = tx_full,
                o_EMPTY       = tx_empty,
                i_WREN        = tx_wren & ~tx_reset,
                i_DI          = tx_wr_d,
                i_RDEN        = tx_rden & ~tx_reset,
                o_DO          = tx_rd_d,
                o_RDCOUNT     = tx_rdcount,
                o_RDERR       = tx_rderr,
                o_WRCOUNT     = tx_wrcount,
                o_WRERR       = tx_wrerr,
            )

            self.comb += [  # Wire up the status signals and interrupts
                self.tx_stat.fields.overflow.eq(tx_wrerr),
                self.tx_stat.fields.underflow.eq(tx_rderr),
                self.tx_stat.fields.free.eq(tx_almostempty),
                self.tx_stat.fields.almostfull.eq(tx_almostfull),
                self.tx_stat.fields.full.eq(tx_full),
                self.tx_stat.fields.empty.eq(tx_empty),
                self.tx_stat.fields.rdcount.eq(tx_rdcount),
                self.tx_stat.fields.wrcount.eq(tx_wrcount),
                self.ev.tx_ready.trigger.eq(tx_almostempty),
                self.ev.tx_error.trigger.eq(tx_wrerr | tx_rderr),
            ]
            self.sync += [
                # This is the bus responder -- need to check how this interacts with uncached memory
                # region
                If(bus.cyc & bus.stb & bus.we & ~bus.ack,
                   If(~tx_full,
                      tx_wr_d.eq(bus.dat_w),
                      tx_wren.eq(1),
                      wr_ack.eq(1),
                   ).Else(
                       tx_wren.eq(0),
                       wr_ack.eq(0),
                   )
                ).Else(
                    tx_wren.eq(0),
                    wr_ack.eq(0),
                )
            ]

            tx_cnt = Signal(5)
            tx_buf = Signal(32)
            self.submodules.txi2s = txi2s = FSM(reset_state="IDLE")
            txi2s.act("IDLE",
                If(self.tx_ctl.fields.enable,
                    If(falling_edge & sync_pin,
                        NextState("WAIT_SYNC"),
                    )
                )
            ),
            txi2s.act("WAIT_SYNC",
                If(falling_edge & ~sync_pin,
                    NextState("LEFT"),
                    NextValue(tx_cnt, 16),
                    NextValue(tx_buf, tx_rd_d),
                    tx_rden.eq(1)
                )
            )
            txi2s.act("LEFT",
                If(~self.tx_ctl.fields.enable,
                    NextState("IDLE")
                ).Else(
                    NextValue(tx_pin, tx_buf[31]),
                    NextValue(tx_buf, Cat(0, tx_buf[:-1])),
                    NextValue(tx_cnt, tx_cnt - 1),
                    NextState("LEFT_WAIT")
                )
            )
            txi2s.act("LEFT_WAIT",
                If(~self.tx_ctl.fields.enable,
                    NextState("IDLE")
                ).Else(
                    If(falling_edge,
                        If((tx_cnt == 0) & sync_pin,
                            NextValue(tx_cnt, 16),
                            NextState("RIGHT")
                        ).Elif(tx_cnt > 0,
                            NextState("LEFT")
                        )
                    )
                )
            )
            txi2s.act("RIGHT",
                If(~self.tx_ctl.fields.enable,
                    NextState("IDLE")
                ).Else(
                    NextValue(tx_pin, tx_buf[31]),
                    NextValue(tx_buf, Cat(0, tx_buf[:-1])),
                    NextValue(tx_cnt, tx_cnt - 1),
                    NextState("RIGHT_WAIT")
                )
            )
            txi2s.act("RIGHT_WAIT",
                If(~self.tx_ctl.fields.enable,
                    NextState("IDLE")
                ).Else(
                    If(falling_edge,
                        If((tx_cnt == 0) & ~sync_pin,
                            NextValue(tx_cnt, 16),
                            NextState("LEFT"),
                            NextValue(tx_buf, tx_rd_d),
                            tx_rden.eq(1)
                        ).Elif(tx_cnt > 0,
                            NextState("RIGHT")
                        )
                    )
                )
            )
