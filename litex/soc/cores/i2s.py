#
# This file is part of LiteX.
#
# Copyright (c) 2020 bunnie <bunnie@kosagi.com>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen.genlib.cdc import MultiReg

from litex.soc.cores.clock import *
from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr_eventmanager import *

from litex.soc.integration.doc import AutoDoc, ModuleDoc
from enum import Enum
import math

from litex.soc.cores.ram.xilinx_fifo_sync_macro import FIFOSyncMacro

class I2S_FORMAT(Enum):
    I2S_STANDARD = 1
    I2S_LEFT_JUSTIFIED = 2

class S7I2S(Module, AutoCSR, AutoDoc):
    def __init__(self, pads, fifo_depth=256, controller=False, master=False, concatenate_channels=True, sample_width=16, frame_format=I2S_FORMAT.I2S_LEFT_JUSTIFIED, lrck_ref_freq=100e6, lrck_freq=44100, bits_per_channel=28, document_interrupts=False, toolchain="vivado"):
        if master == True:
            print("Master/slave terminology deprecated, please use controller/peripheral. Please see http://oshwa.org/a-resolution-to-redefine-spi-signal-names.")
            controller = True

        self.intro = ModuleDoc("""Intro

        I2S controller/peripheral creates a controller/peripheral audio interface instance depending on a configured controller variable.
        Tx and Rx interfaces are inferred based upon the presence or absence of the respective pins in the "pads" argument.

        When device is configured as controller you can manipulate LRCK and SCLK signals using below variables.

        - lrck_ref_freq - is a reference signal that is required to achive desired LRCK and SCLK frequencies.
                         Have be the same as your sys_clk.
        - lrck_freq - this variable defines requested LRCK frequency. Mind you, that based on sys_clk frequency,
                         configured value will be more or less acurate.
        - bits_per_channel - defines SCLK frequency. Mind you, that based on sys_clk frequency,
                         the requested amount of bits per channel may vary from configured.

        When device is configured as peripheral I2S interface, sampling rate and framing is set by the
        programming of the audio CODEC chip. A peripheral configuration defers the
        generation of audio clocks to the CODEC, which has PLLs specialized to generate the correct
        frequencies for audio sampling rates.

        I2S core supports two formats: standard and left-justified.

        - Standard format requires a device to receive and send data with one bit offset for both channels.
            Left channel begins with low signal on LRCK.
        - Left justified format requires from device to receive and send data without any bit offset for both channels.
            Left channel begins with high signal on LRCK.

        Sample width can be any of 1 to 32 bits.

        When sample_width is less than or equal to 16-bit and concatenate_channels is enabled,
        sending and reciving channels is performed atomically. eg. both samples are transfered from/to fifo in single operation.

        System Interface
        ----------------

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
        ---------------

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
        - Words are MSB-to-LSB,
        - Sync is an input or output based on configure mode,
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
        if sample_width > 32:
            sample_width = 32
            print("I2S warning: sample width greater than 32 bits. truncating to 32")

        # Connect pins, synchronizers, and edge detectors
        if hasattr(pads, 'tx'):
            tx_pin = Signal()
            self.comb += pads.tx.eq(tx_pin)
        if hasattr(pads, 'rx'):
            rx_pin = Signal()
            self.specials += MultiReg(pads.rx, rx_pin)

        fifo_data_width = sample_width
        if concatenate_channels:
            if sample_width <= 16:
                fifo_data_width = sample_width * 2
            else:
                concatenate_channels = False
                print("I2S warning: sample width greater than 16 bits. your channels can't be glued")

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
        self.comb += [
            If(bus.we,
                bus.ack.eq(wr_ack),
            ).Else(
                bus.ack.eq(rd_ack),
            )
        ]

        if controller == True:
            if bits_per_channel < sample_width and frame_format == I2S_FORMAT.I2S_STANDARD:
                bits_per_channel = sample_width + 1
                print("I2S warning: bits per channel can't be smaller than sample_width. Setting bits per channel to {}".format(sample_width + 1))
            # implementing LRCK signal
            lrck_period = int(lrck_ref_freq / (lrck_freq * 2))
            lrck_counter = Signal(16)
            self.sync += [
                    If((lrck_counter == lrck_period),
                        lrck_counter.eq(0),
                        pads.sync.eq(~pads.sync),
                    ).Else(
                        lrck_counter.eq(lrck_counter + 1)
                    )
            ]
            # implementing SCLK signal
            sclk_period = int(lrck_period / (bits_per_channel * 2))
            sclk_counter = Signal(16)
            self.sync += [
                    If((sclk_counter == sclk_period),
                        sclk_counter.eq(0),
                        pads.clk.eq(~pads.clk),
                    ).Else(
                        sclk_counter.eq(sclk_counter + 1)
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
            self.rx_ctl = CSRStorage(description="Rx data path control",
                fields=[
                    CSRField("enable", size=1, description="Enable the receiving data"),
                    CSRField("reset",  size=1, description="Writing `1` resets the FIFO. Reset happens regardless of enable state.", pulse=1)
                ])
            self.rx_stat = CSRStatus(description="Rx data path status",
                fields=[
                    CSRField("overflow", size=1, description="Rx overflow"),
                    CSRField("underflow", size=1, description="Rx underflow"),
                    CSRField("dataready", size=1, description="{} words of data loaded and ready to read".format(fifo_depth)),
                    CSRField("empty",     size=1, description="No data available in FIFO to read"), # next flags probably never used
                    CSRField("wrcount",   size=9, description="Write count"),
                    CSRField("rdcount",   size=9, description="Read count"),
                    CSRField("fifo_depth", size=9, description="FIFO depth as synthesized"),
                    CSRField("concatenate_channels", size=1, reset=concatenate_channels, description="Receive and send both channels atomically")
                ])
            self.rx_conf = CSRStatus(description="Rx configuration",
                fields=[
                    CSRField("format", size=2, reset=frame_format.value, description="I2S sample format. {} is left-justified, {} is I2S standard".format(I2S_FORMAT.I2S_LEFT_JUSTIFIED, I2S_FORMAT.I2S_STANDARD)),
                    CSRField("sample_width", size=6, reset=sample_width, description="Single sample width"),
                    CSRField("lrck_freq", size=24, reset=lrck_freq, description="Audio sampling rate frequency"),
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

            self.submodules.rx_fifo = fifo = FIFOSyncMacro("18Kb", data_width=fifo_data_width,
                almost_empty_offset=8, almost_full_offset=(512 - fifo_depth), toolchain=toolchain)
            self.comb += fifo.reset.eq(rx_reset)

            self.comb += [  # Wire up the status signals and interrupts
                self.rx_stat.fields.overflow.eq(fifo.wrerr),
                self.rx_stat.fields.underflow.eq(fifo.rderr),
                self.rx_stat.fields.dataready.eq(fifo.almostfull),
                self.rx_stat.fields.wrcount.eq(fifo.wrcount),
                self.rx_stat.fields.rdcount.eq(fifo.rdcount),
                self.rx_stat.fields.empty.eq(fifo.empty),
                self.ev.rx_ready.trigger.eq(fifo.almostfull),
                self.ev.rx_error.trigger.eq(fifo.wrerr | fifo.rderr),
            ]
            bus_read    = Signal()
            bus_read_d  = Signal()
            rd_ack_pipe = Signal()
            self.comb += bus_read.eq(bus.cyc & bus.stb & ~bus.we & (bus.cti == 0))
            self.sync += [  # This is the bus responder -- only works for uncached memory regions
                bus_read_d.eq(bus_read),
                If(bus_read & ~bus_read_d, # One response, one cycle
                    rd_ack_pipe.eq(1),
                    If(~fifo.empty,
                        bus.dat_r.eq(fifo.rd_d),
                        fifo.rden.eq(~rx_reset),
                    ).Else(
                        # Don't stall the bus indefinitely if we try to read from an empty fifo...just
                        # return garbage
                        bus.dat_r.eq(0xdeadbeef),
                        fifo.rden.eq(0),
                    )
                ).Else(
                    fifo.rden.eq(0),
                    rd_ack_pipe.eq(0),
                ),
                rd_ack.eq(rd_ack_pipe),
            ]
            rx_cnt_width = math.ceil(math.log(fifo_data_width,2))
            rx_cnt = Signal(rx_cnt_width)
            rx_delay_cnt = Signal()
            rx_delay_val = 1 if frame_format == I2S_FORMAT.I2S_STANDARD else 0

            self.submodules.rxi2s = rxi2s = FSM(reset_state="IDLE")
            rxi2s.act("IDLE",
                NextValue(fifo.wr_d, 0),
                If(self.rx_ctl.fields.enable,
                    # Wait_sync guarantees we start at the beginning of a left frame, and not in
                    # the middle
                    If(rising_edge & (~sync_pin if frame_format == I2S_FORMAT.I2S_STANDARD else sync_pin),
                        NextState("WAIT_SYNC"),
                        NextValue(rx_delay_cnt, rx_delay_val)
                    )
                )
            ),
            rxi2s.act("WAIT_SYNC",
                If(rising_edge & (~sync_pin if frame_format == I2S_FORMAT.I2S_STANDARD else sync_pin),
                    If(rx_delay_cnt > 0,
                        NextValue(rx_delay_cnt, rx_delay_cnt - 1),
                        NextState("WAIT_SYNC")
                    ).Else(
                        NextState("LEFT"),
                        NextValue(rx_delay_cnt, rx_delay_val),
                        NextValue(rx_cnt, sample_width)
                    )
                ),
            )
            rxi2s.act("LEFT",
                If(~self.rx_ctl.fields.enable,
                    NextState("IDLE")
                ).Else(
                    NextValue(fifo.wr_d, Cat(rx_pin, fifo.wr_d[:-1])),
                    NextValue(rx_cnt, rx_cnt - 1),
                    NextState("LEFT_WAIT")
                )
            )
            if concatenate_channels:
                rxi2s.act("LEFT_WAIT",
                    If(~self.rx_ctl.fields.enable,
                        NextState("IDLE")
                    ).Else(
                        If(rising_edge,
                            If((rx_cnt == 0),
                                If((sync_pin if frame_format == I2S_FORMAT.I2S_STANDARD else ~sync_pin),
                                    If(rx_delay_cnt == 0,
                                        NextValue(rx_cnt, sample_width),
                                        NextValue(rx_delay_cnt,rx_delay_val),
                                        NextState("RIGHT"),
                                    ).Else(
                                        NextValue(rx_delay_cnt, rx_delay_cnt - 1),
                                        NextState("LEFT_WAIT")
                                    )
                                ).Else(
                                    NextState("LEFT_WAIT")
                                )
                            ).Elif(rx_cnt > 0,
                                NextState("LEFT")
                            )
                        )
                    )
                )
            else:
                rxi2s.act("LEFT_WAIT",
                    If(~self.rx_ctl.fields.enable,
                        NextState("IDLE")
                    ).Else(
                        If(rising_edge,
                            If((rx_cnt == 0),
                                If((sync_pin if frame_format == I2S_FORMAT.I2S_STANDARD else ~sync_pin),
                                    If(rx_delay_cnt == 0,
                                        NextValue(rx_cnt, sample_width),
                                        NextValue(rx_delay_cnt,rx_delay_val),
                                        NextState("RIGHT"),
                                        fifo.wren.eq(~rx_reset) # Pulse rx_wren to write the current data word
                                    ).Else(
                                        NextValue(rx_delay_cnt, rx_delay_cnt - 1),
                                        NextState("LEFT_WAIT")
                                    )
                                ).Else(
                                    NextState("LEFT_WAIT")
                                )
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
                    NextValue(fifo.wr_d, Cat(rx_pin, fifo.wr_d[:-1])),
                    NextValue(rx_cnt, rx_cnt - 1),
                    NextState("RIGHT_WAIT")
                )
            )
            rxi2s.act("RIGHT_WAIT",
                If(~self.rx_ctl.fields.enable,
                    NextState("IDLE")
                ).Else(
                    If(rising_edge,
                        If((rx_cnt == 0) & (~sync_pin if frame_format == I2S_FORMAT.I2S_STANDARD else sync_pin),
                            If(rx_delay_cnt == 0,
                                NextValue(rx_cnt, sample_width),
                                NextValue(rx_delay_cnt,rx_delay_val),
                                NextState("LEFT"),
                                fifo.wren.eq(~rx_reset) # Pulse rx_wren to write the current data word
                            ).Else(
                                NextValue(rx_delay_cnt, rx_delay_cnt - 1),
                                NextState("RIGHT_WAIT")
                            )
                        ).Elif(rx_cnt > 0,
                            NextState("RIGHT")
                        )
                    )
                )
            )


        # Build the TX subsystem
        if hasattr(pads, 'tx'):
            self.tx_ctl = CSRStorage(description="Tx data path control",
                fields=[
                    CSRField("enable", size=1, description="Enable the transmission data"),
                    CSRField("reset",  size=1, description="Writing `1` resets the FIFO. Reset happens regardless of enable state.", pulse=1)
                ])
            self.tx_stat = CSRStatus(description="Tx data path status",
                fields=[
                    CSRField("overflow",  size=1, description="Tx overflow"),
                    CSRField("underflow",  size=1, description="Tx underflow"),
                    CSRField("free",       size=1, description="At least {} words of space free".format(fifo_depth)),
                    CSRField("almostfull", size=1, description="Less than 8 words space available"), # the next few flags should be rarely used
                    CSRField("full",       size=1, description="FIFO is full or overfull"),
                    CSRField("empty",      size=1, description="FIFO is empty"),
                    CSRField("wrcount",    size=9, description="Tx write count"),
                    CSRField("rdcount",    size=9, description="Tx read count"),
                    CSRField("concatenate_channels", size=1, reset=concatenate_channels, description="Receive and send both channels atomically")
                ])
            self.tx_conf = CSRStatus(description="TX configuration",
                fields=[
                    CSRField("format", size=2, reset=frame_format.value, description="I2S sample format. {} is left-justified, {} is I2S standard".format(I2S_FORMAT.I2S_LEFT_JUSTIFIED, I2S_FORMAT.I2S_STANDARD)),
                    CSRField("sample_width", size=6, reset=sample_width, description="Single sample width"),
                    CSRField("lrck_freq", size=24, reset=lrck_freq, description="Audio sampling rate frequency"),
                ])


            tx_rst_cnt = Signal(3)
            tx_reset = Signal()

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

            self.submodules.tx_fifo = fifo = FIFOSyncMacro("18Kb", data_width=fifo_data_width,
                almost_empty_offset=(512 - fifo_depth), almost_full_offset=8, toolchain=toolchain)
            self.comb += fifo.reset.eq(tx_reset)

            self.comb += [  # Wire up the status signals and interrupts
                self.tx_stat.fields.underflow.eq(fifo.rderr),
                self.tx_stat.fields.free.eq(fifo.almostempty),
                self.tx_stat.fields.almostfull.eq(fifo.almostfull),
                self.tx_stat.fields.full.eq(fifo.full),
                self.tx_stat.fields.empty.eq(fifo.empty),
                self.tx_stat.fields.rdcount.eq(fifo.rdcount),
                self.tx_stat.fields.wrcount.eq(fifo.wrcount),
                self.ev.tx_ready.trigger.eq(fifo.almostempty),
                self.ev.tx_error.trigger.eq(fifo.wrerr | fifo.rderr),
            ]
            self.sync += [
                # This is the bus responder -- need to check how this interacts with uncached memory
                # region
                If(bus.cyc & bus.stb & bus.we & ~bus.ack,
                    If(~fifo.full,
                        fifo.wr_d.eq(bus.dat_w),
                        fifo.wren.eq(~tx_reset),
                        wr_ack.eq(1),
                    ).Else(
                        fifo.wren.eq(0),
                        wr_ack.eq(0),
                    )
                ).Else(
                    fifo.wren.eq(0),
                    wr_ack.eq(0),
                )
            ]

            tx_buf_width = fifo_data_width + 1 if frame_format == I2S_FORMAT.I2S_STANDARD else fifo_data_width
            sample_width = sample_width + 1 if frame_format == I2S_FORMAT.I2S_STANDARD else sample_width
            offset = [0] if frame_format == I2S_FORMAT.I2S_STANDARD else []

            tx_cnt_width = math.ceil(math.log(fifo_data_width,2))
            tx_cnt = Signal(tx_cnt_width)
            tx_buf = Signal(tx_buf_width)
            sample_msb = fifo_data_width - 1
            self.submodules.txi2s = txi2s = FSM(reset_state="IDLE")
            txi2s.act("IDLE",
                If(self.tx_ctl.fields.enable,
                    If(rising_edge & (~sync_pin if frame_format == I2S_FORMAT.I2S_STANDARD else sync_pin),
                        NextState("WAIT_SYNC"),
                    )
                )
            ),
            txi2s.act("WAIT_SYNC",
                If(rising_edge & (~sync_pin if frame_format == I2S_FORMAT.I2S_STANDARD else sync_pin),
                    NextState("LEFT_FALL"),
                    NextValue(tx_cnt, sample_width),
                    NextValue(tx_buf, Cat(fifo.rd_d, offset)),
                    fifo.rden.eq(~tx_reset),
                )
            )
            # sync should be sampled on rising edge, but data should change on falling edge
            txi2s.act("LEFT_FALL",
                If(falling_edge,
                    NextState("LEFT")
                )
            )
            txi2s.act("LEFT",
                If(~self.tx_ctl.fields.enable,
                    NextState("IDLE")
                ).Else(
                    NextValue(tx_pin, tx_buf[sample_msb]),
                    NextValue(tx_buf, Cat(0, tx_buf[:-1])),
                    NextValue(tx_cnt, tx_cnt - 1),
                    NextState("LEFT_WAIT")
                )
            )
            if concatenate_channels:
                txi2s.act("LEFT_WAIT",
                    If(~self.tx_ctl.fields.enable,
                        NextState("IDLE")
                    ).Else(
                        If(rising_edge,
                            If((tx_cnt == 0),
                                If((sync_pin if frame_format == I2S_FORMAT.I2S_STANDARD else ~sync_pin),
                                    NextValue(tx_cnt, sample_width),
                                    NextState("RIGHT"),
                                ).Else(
                                    NextState("LEFT_WAIT"),
                                )
                            ).Elif(tx_cnt > 0,
                                NextState("LEFT_FALL"),
                            )
                        )
                    )
                )
            else:
                txi2s.act("LEFT_WAIT",
                    If(~self.tx_ctl.fields.enable,
                        NextState("IDLE")
                    ).Else(
                        If(rising_edge,
                            If((tx_cnt == 0),
                                If((sync_pin if frame_format == I2S_FORMAT.I2S_STANDARD else ~sync_pin),
                                    NextValue(tx_cnt, sample_width),
                                    NextState("RIGHT_FALL"),
                                    NextValue(tx_buf, Cat(fifo.rd_d,offset)),
                                    fifo.rden.eq(~tx_reset),
                                ).Else(
                                    NextState("LEFT_WAIT"),
                                )
                            ).Elif(tx_cnt > 0,
                                NextState("LEFT_FALL"),
                            )
                        )
                    )
                )
            # sync should be sampled on rising edge, but data should change on falling edge
            txi2s.act("RIGHT_FALL",
                If(falling_edge,
                    NextState("RIGHT")
                )
            )
            txi2s.act("RIGHT",
                If(~self.tx_ctl.fields.enable,
                    NextState("IDLE")
                ).Else(
                    NextValue(tx_pin, tx_buf[sample_msb]),
                    NextValue(tx_buf, Cat(0, tx_buf[:-1])),
                    NextValue(tx_cnt, tx_cnt - 1),
                    NextState("RIGHT_WAIT")
                )
            )
            txi2s.act("RIGHT_WAIT",
                If(~self.tx_ctl.fields.enable,
                    NextState("IDLE")
                ).Else(
                    If(rising_edge,
                        If((tx_cnt == 0) & (~sync_pin if frame_format == I2S_FORMAT.I2S_STANDARD else sync_pin),
                            NextValue(tx_cnt, sample_width),
                            NextState("LEFT_FALL"),
                            NextValue(tx_buf, Cat(fifo.rd_d,offset)),
                            fifo.rden.eq(~tx_reset)
                        ).Elif(tx_cnt > 0,
                            NextState("RIGHT_FALL")
                        )
                    )
                )
            )
