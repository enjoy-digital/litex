#
# This file is part of LiteX.
#
# Copyright (c) 2023 Andrew Dennison <andrew@motec.com.au>
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Shared helpers for the LiteX unit test suite.

Only place things here once they are duplicated by two or more test files.
"""

from migen import *


# Tristate mock ----------------------------------------------------------------------------------

class _MockTristateImpl(Module):
    def __init__(self, t):
        t.i_mock = Signal(reset=True)
        # Always drive the pad; only drive `i` if the consumer requested one (some Tristate
        # instantiations — e.g. bitbang I2CMaster's SCL — pass no `i`).
        self.comb += If(t.oe,
            t.target.eq(t.o),
        ).Else(
            t.target.eq(t.i_mock),
        )
        if t.i is not None:
            self.comb += If(t.oe,
                t.i.eq(t.o),
            ).Else(
                t.i.eq(t.i_mock),
            )


class MockTristate:
    """A mock for migen's Tristate special that's usable in `run_simulation`.

    Usage:
        from migen.fhdl.specials import Tristate
        from test.common import MockTristate
        run_simulation(dut, gen(), special_overrides={Tristate: MockTristate})

    The input side (`t.i`, if present) tracks the output (`t.o`) when `t.oe=1`, and otherwise
    tracks a new `t.i_mock` `Signal` (default=1) that generators can drive to simulate an
    external device pulling the line.
    """

    @staticmethod
    def lower(t):
        return _MockTristateImpl(t)
