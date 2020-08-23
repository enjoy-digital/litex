#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# SPDX-License-Identifier: BSD-2-Clause

from operator import xor, add
from functools import reduce

from migen import *
from migen.genlib.cdc import MultiReg

# PRBS Generators ----------------------------------------------------------------------------------

class PRBSGenerator(Module):
    def __init__(self, n_out, n_state=23, taps=[17, 22]):
        self.o = Signal(n_out)

        # # #

        state = Signal(n_state, reset=1)
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
        self.i = Signal(width)
        self.o = Signal(width)

        # # #

        config = Signal(2)

        # generators
        self.specials += MultiReg(self.config, config)
        prbs7 = PRBS7Generator(width)
        prbs15 = PRBS15Generator(width)
        prbs31 = PRBS31Generator(width)
        self.submodules += prbs7, prbs15, prbs31

        # select
        prbs_data = Signal(width)
        self.comb += \
            If(config == 0b11,
                prbs_data.eq(prbs31.o)
            ).Elif(config == 0b10,
                prbs_data.eq(prbs15.o)
            ).Else(
                prbs_data.eq(prbs7.o)
            )

        # optional bits reversing
        if reverse:
            new_prbs_data = Signal(width)
            self.comb += new_prbs_data.eq(prbs_data[::-1])
            prbs_data = new_prbs_data

        # prbs / data mux
        self.comb += \
            If(config == 0,
                self.o.eq(self.i)
            ).Else(
                self.o.eq(prbs_data)
            )

# PRBS Checkers ------------------------------------------------------------------------------------

class PRBSChecker(Module):
    def __init__(self, n_in, n_state=23, taps=[17, 22]):
        self.i = Signal(n_in)
        self.errors = Signal(n_in)

        # # #

        state = Signal(n_state, reset=1)
        curval = [state[i] for i in range(n_state)]
        for i in reversed(range(n_in)):
            correctv = reduce(xor, [curval[tap] for tap in taps])
            self.sync += self.errors[i].eq(self.i[i] != correctv)
            curval.insert(0, self.i[i])
            curval.pop()

        self.sync += state.eq(Cat(*curval[:n_state]))


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
    def __init__(self, width, reverse=False):
        self.i = Signal(width)
        self.config = Signal(2)
        self.errors = Signal(32)

        # # #

        config = Signal(2)

        # optional bits reversing
        prbs_data = self.i
        if reverse:
            new_prbs_data = Signal(width)
            self.comb += new_prbs_data.eq(prbs_data[::-1])
            prbs_data = new_prbs_data

        # checkers
        self.specials += MultiReg(self.config, config)
        prbs7 = PRBS7Checker(width)
        prbs15 = PRBS15Checker(width)
        prbs31 = PRBS31Checker(width)
        self.submodules += prbs7, prbs15, prbs31
        self.comb += [
            prbs7.i.eq(prbs_data),
            prbs15.i.eq(prbs_data),
            prbs31.i.eq(prbs_data)
        ]

        # errors count
        self.sync += \
            If(config == 0,
                self.errors.eq(0)
            ).Elif(self.errors != (2**32-1),
                If(config == 0b01,
                    self.errors.eq(self.errors + (prbs7.errors != 0))
                ).Elif(config == 0b10,
                    self.errors.eq(self.errors + (prbs15.errors != 0))
                ).Elif(config == 0b11,
                    self.errors.eq(self.errors + (prbs31.errors != 0))
                )
            )
