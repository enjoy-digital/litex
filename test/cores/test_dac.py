#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.dac import DAC


def sigma_delta_model(value, data_width, cycles):
    accum = 0
    mask  = 2**data_width - 1
    out   = []
    for i in range(cycles):
        out.append((accum >> data_width) & 0x1)
        accum = (accum & mask) + value
    return out


def constant_transition_model(value, data_width, cycles):
    accum = 0
    phase = 0
    mask  = 2**data_width - 1
    out   = []
    for i in range(cycles):
        sd_bit = (accum >> data_width) & 0x1
        out.append({
            0 : 1,
            1 : sd_bit,
            2 : 0,
        }[phase])
        if phase == 2:
            phase = 0
            accum = (accum & mask) + value
        else:
            phase += 1
    return out


class TestDAC(unittest.TestCase):
    def run_dac(self, value, data_width=4, cycles=32, with_constant_transition=False):
        out = Signal()
        dut = DAC(
            out                      = out,
            data_width               = data_width,
            with_csr                 = False,
            with_constant_transition = with_constant_transition,
        )
        dut.value.reset = value
        samples = []

        def generator(dut):
            for i in range(cycles):
                samples.append((yield out))
                yield

        run_simulation(dut, generator(dut))
        return samples

    def test_sigma_delta(self):
        self.assertEqual(
            self.run_dac(value=9, data_width=4, cycles=32),
            sigma_delta_model(value=9, data_width=4, cycles=32),
        )

    def test_constant_transition(self):
        self.assertEqual(
            self.run_dac(value=9, data_width=4, cycles=32, with_constant_transition=True),
            constant_transition_model(value=9, data_width=4, cycles=32),
        )

    def test_constant_transition_zero_pattern(self):
        self.assertEqual(
            self.run_dac(value=0, data_width=4, cycles=9, with_constant_transition=True),
            [1, 0, 0] * 3,
        )
