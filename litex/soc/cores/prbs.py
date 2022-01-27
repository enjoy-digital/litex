#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# SPDX-License-Identifier: BSD-2-Clause

from operator import xor, add
from functools import reduce

from migen import *
from migen.genlib.misc import WaitTimer
from migen.genlib.cdc import MultiReg

# Constants ----------------------------------------------------------------------------------------

PRBS_CONFIG_OFF    = 0b00
PRBS_CONFIG_PRBS7  = 0b01
PRBS_CONFIG_PRBS15 = 0b10
PRBS_CONFIG_PRBS31 = 0b11

# PRBS Generators ----------------------------------------------------------------------------------

class PRBSGenerator(Module):
    def __init__(self, n_out, n_state=23, taps=[17, 22]):
        self.o = Signal(n_out)

        # # #

        state  = Signal(n_state, reset=1)
        curval = [state[i] for i in range(n_state)]
        curval += [0]*(n_out - n_state)
        for i in range(n_out):
            nv = reduce(xor, [curval[tap] for tap in taps])
            curval.insert(0, nv)
            curval.pop()

        self.sync += [
            state.eq(Cat(*curval[:n_state])),
            self.o.eq(Cat(*curval))
        ]


class PRBS7Generator(PRBSGenerator):
    def __init__(self, n_out):
        PRBSGenerator.__init__(self, n_out, n_state=7, taps=[5, 6])


class PRBS15Generator(PRBSGenerator):
    def __init__(self, n_out):
        PRBSGenerator.__init__(self, n_out, n_state=15, taps=[13, 14])


class PRBS31Generator(PRBSGenerator):
    def __init__(self, n_out):
        PRBSGenerator.__init__(self, n_out, n_state=31, taps=[27, 30])

# PRBS TX ------------------------------------------------------------------------------------------

class PRBSTX(Module):
    def __init__(self, width, reverse=False):
        self.config = Signal(2)
        self.i      = Signal(width)
        self.o      = Signal(width)

        # # #

        config = Signal(2)

        # Generators.
        self.specials += MultiReg(self.config, config)
        prbs7  = PRBS7Generator(width)
        prbs15 = PRBS15Generator(width)
        prbs31 = PRBS31Generator(width)
        self.submodules += prbs7, prbs15, prbs31

        # PRBS Selection.
        prbs_data = Signal(width)
        self.comb += Case(self.config, {
            PRBS_CONFIG_OFF    : prbs_data.eq(0),
            PRBS_CONFIG_PRBS7  : prbs_data.eq(prbs7.o),
            PRBS_CONFIG_PRBS15 : prbs_data.eq(prbs15.o),
            PRBS_CONFIG_PRBS31 : prbs_data.eq(prbs31.o),
        })

        # Optional Bits Reversing.
        if reverse:
            new_prbs_data = Signal(width)
            self.comb += new_prbs_data.eq(prbs_data[::-1])
            prbs_data = new_prbs_data

        # PRBS / Data Selection.
        self.comb += [
            self.o.eq(self.i),
            If(config != 0,
                self.o.eq(prbs_data)
            )
        ]

# PRBS Checkers ------------------------------------------------------------------------------------

class PRBSChecker(Module):
    def __init__(self, n_in, n_state=23, taps=[17, 22]):
        self.i      = Signal(n_in)
        self.errors = Signal(n_in)

        # # #

        # LFSR Update / Check.
        state  = Signal(n_state, reset=1)
        curval = [state[i] for i in range(n_state)]
        for i in reversed(range(n_in)):
            correctv = reduce(xor, [curval[tap] for tap in taps])
            self.comb += self.errors[i].eq(self.i[i] != correctv)
            curval.insert(0, self.i[i])
            curval.pop()
        self.sync += state.eq(Cat(*curval[:n_state]))

        # Idle Check.
        i_last     = Signal(n_in)
        idle_timer = WaitTimer(1024)
        self.submodules += idle_timer
        self.sync += i_last.eq(self.i)
        self.comb += idle_timer.wait.eq(self.i == i_last)
        self.comb += If(idle_timer.done, self.errors.eq(2**n_in-1))

class PRBS7Checker(PRBSChecker):
    def __init__(self, n_out):
        PRBSChecker.__init__(self, n_out, n_state=7, taps=[5, 6])


class PRBS15Checker(PRBSChecker):
    def __init__(self, n_out):
        PRBSChecker.__init__(self, n_out, n_state=15, taps=[13, 14])


class PRBS31Checker(PRBSChecker):
    def __init__(self, n_out):
        PRBSChecker.__init__(self, n_out, n_state=31, taps=[27, 30])

# PRBS RX ------------------------------------------------------------------------------------------

class PRBSRX(Module):
    def __init__(self, width, reverse=False, with_errors_saturation=False):
        self.config = Signal(2)
        self.pause  = Signal()
        self.i      = Signal(width)
        self.errors = errors = Signal(32)

        # # #

        config = Signal(2)

        # Optional bits reversing.
        prbs_data = self.i
        if reverse:
            new_prbs_data = Signal(width)
            self.comb += new_prbs_data.eq(prbs_data[::-1])
            prbs_data = new_prbs_data

        # Checkers.
        self.specials += MultiReg(self.config, config)
        prbs7  = PRBS7Checker(width)
        prbs15 = PRBS15Checker(width)
        prbs31 = PRBS31Checker(width)
        self.submodules += prbs7, prbs15, prbs31
        self.comb += [
            prbs7.i.eq( prbs_data),
            prbs15.i.eq(prbs_data),
            prbs31.i.eq(prbs_data),
        ]

        # Errors count (with optional saturation).
        self.sync += [
            If(config == PRBS_CONFIG_OFF,
                errors.eq(0)
            ).Elif(~self.pause & (~with_errors_saturation | (errors != (2**32-1))),
                If(config == PRBS_CONFIG_PRBS7,
                    errors.eq(errors + (prbs7.errors != 0))
                ),
                If(config == PRBS_CONFIG_PRBS15,
                    errors.eq(errors + (prbs15.errors != 0))
                ),
                If(config == PRBS_CONFIG_PRBS31,
                    errors.eq(errors + (prbs31.errors != 0))
                )
            )
        ]
