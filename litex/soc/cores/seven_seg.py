#
# This file is part of LiteX.
#
# Copyright (c) 2026 Paul Hamshere <p.w.hamshere@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.soc.interconnect.csr import *

# Seven Segment Display ----------------------------------------------------------------------------

_HEX2SEG = Array([
    0x3f, 0x06, 0x5b, 0x4f, 0x66, 0x6d, 0x7d, 0x07,
    0x7f, 0x6f, 0x77, 0x7c, 0x39, 0x5e, 0x79, 0x71,
])


class SevenSegmentDisplay(LiteXModule):
    def __init__(self, sys_clk_freq, segments_pads, anodes_pads,
        refresh_rate       = 1e3,
        segment_active_low = True,
        digit_active_low   = True):
        n_segments = len(segments_pads)
        n_digits   = len(anodes_pads)
        if n_segments not in [7, 8]:
            raise ValueError("segments_pads must expose 7 or 8 signals")
        if n_digits <= 0:
            raise ValueError("anodes_pads must expose at least one signal")
        if refresh_rate <= 0:
            raise ValueError("refresh_rate must be greater than 0")

        refresh_cycles = int(sys_clk_freq/(refresh_rate*n_digits))
        if refresh_cycles <= 0:
            raise ValueError("sys_clk_freq too low for selected refresh_rate")

        self.n_segments     = n_segments
        self.n_digits       = n_digits
        self.refresh_cycles = refresh_cycles
        self.values         = CSRStorage(4*n_digits, description=
            "Packed hexadecimal digit values. Digit 0 uses bits 3:0.")

        # # #

        digit            = Signal(max=max(n_digits, 2))
        digit_value      = Signal(4)
        digit_onehot     = Signal(n_digits)
        decoded_segments = Signal(n_segments)
        refresh_counter  = Signal(max=max(refresh_cycles, 2))

        cases = {}
        for n in range(n_digits):
            cases[n] = [
                digit_value.eq(self.values.storage[4*n:4*(n + 1)]),
                digit_onehot.eq(1 << n),
            ]
        cases["default"] = cases[0]

        segment_invert = segment_active_low*((2**n_segments) - 1)
        digit_invert   = digit_active_low*((2**n_digits) - 1)

        self.comb += [
            Case(digit, cases),
            decoded_segments.eq(_HEX2SEG[digit_value]),
            segments_pads.eq(decoded_segments ^ segment_invert),
            anodes_pads.eq(digit_onehot ^ digit_invert),
        ]

        self.sync += [
            If(refresh_counter == (refresh_cycles - 1),
                refresh_counter.eq(0),
                If(digit == (n_digits - 1),
                    digit.eq(0)
                ).Else(
                    digit.eq(digit + 1)
                )
            ).Else(
                refresh_counter.eq(refresh_counter + 1)
            )
        ]
