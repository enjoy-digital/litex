#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import MultiReg

from litex.gen import *

from litex.soc.interconnect import stream

# ADAT Lightpipe -----------------------------------------------------------------------------------

ADAT_CHANNELS     = 8
ADAT_SAMPLE_WIDTH = 24
ADAT_FRAME_BITS   = 256
ADAT_SYNC_BITS    = 10


def _adat_frame(samples, user):
    bits = []

    # Synchronization sequence.
    bits += [Constant(0, 1) for _ in range(10)]

    # User bits, framed with transition bits.
    bits += [Constant(1, 1), user[3], user[2], user[1], user[0], Constant(1, 1)]

    # Samples: 6 x 4-bit nibbles, each followed by a transition bit.
    for sample in samples:
        for nibble in range(6):
            for bit in range(4):
                bits.append(sample[ADAT_SAMPLE_WIDTH - 1 - 4*nibble - bit])
            bits.append(Constant(1, 1))

    assert len(bits) == ADAT_FRAME_BITS
    return Cat(*bits)


class ADATClkPhaseAccum(LiteXModule):
    def __init__(self, tuning_word):
        self.tick = Signal()

        # # #

        phase = Signal(32, reset_less=True)
        self.sync += Cat(phase, self.tick).eq(phase + tuning_word)


class ADATTX(LiteXModule):
    """ADAT Lightpipe transmitter.

    The core implements the common 8-channel / 24-bit ADAT transmit framing:
    10 sync bits, 4 user bits, 8 audio samples and NRZI line encoding.

    Samples are accepted one channel at a time on ``sink``. Once 8 samples have
    been received, they are used at the next ADAT frame boundary. If no complete
    frame is available, the previous samples are repeated and ``underflow`` is
    pulsed.

    When ``sys_clk_freq`` is provided, a phase accumulator generates the ADAT
    bit tick. Otherwise, ``bit_tick`` must be driven externally, which is the
    preferred mode when a low-jitter audio/ADAT clock is available.
    """
    def __init__(self, pads=None, sys_clk_freq=None, sample_rate=48e3):
        self.sink = sink = stream.Endpoint([("data", ADAT_SAMPLE_WIDTH)])
        self.user = Signal(4)

        self.tx          = Signal()
        self.bit_tick    = Signal()
        self.frame_start = Signal()
        self.underflow   = Signal()

        # # #

        if pads is not None:
            tx = pads.tx if hasattr(pads, "tx") else pads
            self.comb += tx.eq(self.tx)

        if sys_clk_freq is not None:
            bit_rate = sample_rate*ADAT_FRAME_BITS
            if bit_rate >= sys_clk_freq:
                raise ValueError("ADAT bit rate must be lower than sys_clk_freq.")
            tuning_word = int((bit_rate/sys_clk_freq)*2**32)
            self.clk_phase_accum = ADATClkPhaseAccum(tuning_word)
            self.comb += self.bit_tick.eq(self.clk_phase_accum.tick)

        samples      = [Signal(ADAT_SAMPLE_WIDTH) for _ in range(ADAT_CHANNELS)]
        next_samples = [Signal(ADAT_SAMPLE_WIDTH) for _ in range(ADAT_CHANNELS)]

        frame      = Signal(ADAT_FRAME_BITS)
        next_frame = Signal(ADAT_FRAME_BITS)
        self.comb += [
            frame.eq(_adat_frame(samples, self.user)),
            next_frame.eq(_adat_frame(next_samples, self.user)),
        ]

        # Input sample buffering.
        next_sample  = Array(next_samples)
        sample_count = Signal(max=ADAT_CHANNELS)
        frame_ready  = Signal()
        sink_fire    = Signal()

        self.comb += [
            sink.ready.eq(~frame_ready),
            sink_fire.eq(sink.valid & sink.ready),
        ]

        self.sync += If(sink_fire,
            next_sample[sample_count].eq(sink.data),
            If(sample_count == (ADAT_CHANNELS - 1),
                sample_count.eq(0),
                frame_ready.eq(1),
            ).Else(
                sample_count.eq(sample_count + 1),
            )
        )

        # Output serializer.
        shift     = Signal(ADAT_FRAME_BITS)
        bit_count = Signal(max=ADAT_FRAME_BITS)

        load_next_frame = [
            frame_ready.eq(0),
        ]
        for n in range(ADAT_CHANNELS):
            load_next_frame.append(samples[n].eq(next_samples[n]))

        self.sync += [
            self.frame_start.eq(0),
            self.underflow.eq(0),
            If(self.bit_tick,
                If(shift[0],
                    self.tx.eq(~self.tx),
                ),
                If(bit_count == (ADAT_FRAME_BITS - 1),
                    bit_count.eq(0),
                    self.frame_start.eq(1),
                    shift.eq(Mux(frame_ready, next_frame, frame)),
                    If(frame_ready,
                        *load_next_frame
                    ).Else(
                        self.underflow.eq(1),
                    )
                ).Else(
                    bit_count.eq(bit_count + 1),
                    shift.eq(Cat(shift[1:], 0)),
                )
            )
        ]


class ADATRX(LiteXModule):
    """ADAT Lightpipe receiver.

    This is a digital ADAT frame decoder. It samples an NRZI encoded ADAT line
    on ``bit_tick``, detects the 10-zero-bit synchronization sequence, extracts
    the 4 user bits and emits the 8 received 24-bit audio samples on ``source``.

    As with ``ADATTX``, ``sys_clk_freq`` can be used to generate a nominal bit
    tick, but robust asynchronous reception should use a hardware-specific clock
    recovery/oversampling front-end and drive ``bit_tick`` from it.
    """
    def __init__(self, pads=None, sys_clk_freq=None, sample_rate=48e3):
        self.source = source = stream.Endpoint([
            ("data",    ADAT_SAMPLE_WIDTH),
            ("channel", 3),
        ])
        self.user = Signal(4)

        self.rx          = Signal()
        self.bit_tick    = Signal()
        self.frame_start = Signal()
        self.locked      = Signal()
        self.invalid     = Signal()
        self.overflow    = Signal()

        # # #

        if pads is not None:
            rx = pads.rx if hasattr(pads, "rx") else pads
            self.specials += MultiReg(rx, self.rx)

        if sys_clk_freq is not None:
            bit_rate = sample_rate*ADAT_FRAME_BITS
            if bit_rate >= sys_clk_freq:
                raise ValueError("ADAT bit rate must be lower than sys_clk_freq.")
            tuning_word = int((bit_rate/sys_clk_freq)*2**32)
            self.clk_phase_accum = ADATClkPhaseAccum(tuning_word)
            self.comb += self.bit_tick.eq(self.clk_phase_accum.tick)

        SEARCH, USER, USER_MARKER, SAMPLE_DATA, SAMPLE_MARKER = range(5)

        state        = Signal(3)
        rx_last      = Signal()
        decoded_bit  = Signal()
        zero_count   = Signal(max=ADAT_SYNC_BITS + 1)
        user_shift   = Signal(4)
        user_count   = Signal(max=4)
        sample_shift = Signal(ADAT_SAMPLE_WIDTH)
        sample_bit   = Signal(max=4)
        nibble       = Signal(max=6)
        channel      = Signal(max=ADAT_CHANNELS)

        source_free = Signal()
        self.comb += [
            decoded_bit.eq(self.rx ^ rx_last),
            source_free.eq(~source.valid | source.ready),
        ]

        emit_sample = [
            If(source_free,
                source.valid.eq(1),
                source.data.eq(sample_shift),
                source.channel.eq(channel),
                source.first.eq(channel == 0),
                source.last.eq(channel == (ADAT_CHANNELS - 1)),
            ).Else(
                self.overflow.eq(1),
            )
        ]

        restart_search = [
            state.eq(SEARCH),
            zero_count.eq(Mux(decoded_bit, 0, 1)),
            self.locked.eq(0),
            self.invalid.eq(1),
        ]

        self.sync += [
            self.frame_start.eq(0),
            self.invalid.eq(0),
            self.overflow.eq(0),

            If(source.valid & source.ready,
                source.valid.eq(0),
            ),

            If(self.bit_tick,
                rx_last.eq(self.rx),
                Case(state, {
                    SEARCH: [
                        If(decoded_bit,
                            If(zero_count == ADAT_SYNC_BITS,
                                state.eq(USER),
                                self.locked.eq(1),
                                self.frame_start.eq(1),
                                zero_count.eq(0),
                                user_count.eq(0),
                                user_shift.eq(0),
                            ).Else(
                                zero_count.eq(0),
                            )
                        ).Else(
                            If(zero_count < ADAT_SYNC_BITS,
                                zero_count.eq(zero_count + 1),
                            )
                        )
                    ],
                    USER: [
                        user_shift.eq(Cat(decoded_bit, user_shift[:3])),
                        If(user_count == 3,
                            user_count.eq(0),
                            state.eq(USER_MARKER),
                        ).Else(
                            user_count.eq(user_count + 1),
                        )
                    ],
                    USER_MARKER: [
                        If(decoded_bit,
                            self.user.eq(user_shift),
                            state.eq(SAMPLE_DATA),
                            sample_shift.eq(0),
                            sample_bit.eq(0),
                            nibble.eq(0),
                            channel.eq(0),
                        ).Else(
                            *restart_search
                        )
                    ],
                    SAMPLE_DATA: [
                        sample_shift.eq(Cat(decoded_bit, sample_shift[:ADAT_SAMPLE_WIDTH - 1])),
                        If(sample_bit == 3,
                            sample_bit.eq(0),
                            state.eq(SAMPLE_MARKER),
                        ).Else(
                            sample_bit.eq(sample_bit + 1),
                        )
                    ],
                    SAMPLE_MARKER: [
                        If(decoded_bit,
                            If(nibble == 5,
                                *emit_sample,
                                sample_shift.eq(0),
                                nibble.eq(0),
                                If(channel == (ADAT_CHANNELS - 1),
                                    channel.eq(0),
                                    state.eq(SEARCH),
                                    zero_count.eq(0),
                                ).Else(
                                    channel.eq(channel + 1),
                                    state.eq(SAMPLE_DATA),
                                )
                            ).Else(
                                nibble.eq(nibble + 1),
                                state.eq(SAMPLE_DATA),
                            )
                        ).Else(
                            *restart_search
                        )
                    ],
                })
            )
        ]
