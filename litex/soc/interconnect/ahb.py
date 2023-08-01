#
# This file is part of LiteX.
#
# Copyright (c) 2021 Ilia Sergachev <ilia.sergachev@protonmail.ch>
# Copyright (c) 2023 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""AHB support for LiteX"""

from enum import IntEnum

from migen import *

from litex.gen import *

# Helpers ------------------------------------------------------------------------------------------

class TransferType(IntEnum):
    """Defines types of AHB transfers."""
    IDLE          = 0
    BUSY          = 1
    NONSEQUENTIAL = 2
    SEQUENTIAL    = 3

# AHB Interface ------------------------------------------------------------------------------------

class Interface(Record):
    """Sets up the AHB interface signals for master and slave."""
    adr_width      = 32
    data_width     = 32
    master_signals = [
        ("addr",     adr_width),
        ("burst",    3),
        ("mastlock", 1),
        ("prot",     4),
        ("size",     3),
        ("trans",    2),
        ("wdata",    data_width),
        ("write",    1),
        ("sel",      1),
    ]
    slave_signals = [
        ("rdata",    data_width),
        ("readyout", 1),
        ("resp",     1),
    ]
    def __init__(self):
        Record.__init__(self, set_layout_parameters(self.master_signals + self.slave_signals))

# AHB to Wishbone  ---------------------------------------------------------------------------------

class AHB2Wishbone(LiteXModule):
    """
    This module converts AHB protocol transactions to the Wishbone protocol.

    It takes as input an AHB interface and a Wishbone interface and does the conversion.
    """
    def __init__(self, ahb, wishbone):
        wishbone_adr_shift = log2_int(ahb.data_width // 8)
        assert ahb.data_width == wishbone.data_width
        assert ahb.adr_width == wishbone.adr_width + wishbone_adr_shift

        self.comb += ahb.resp.eq(wishbone.err)

        self.fsm = fsm = FSM()
        fsm.act("IDLE",
            ahb.readyout.eq(1),
            If(ahb.sel &
              (ahb.size  == wishbone_adr_shift) &
              (ahb.trans == TransferType.NONSEQUENTIAL),
               NextValue(wishbone.adr, ahb.addr[2:]),
               NextValue(wishbone.dat_w, ahb.wdata),
               NextValue(wishbone.we, ahb.write),
               NextValue(wishbone.sel, 2**len(wishbone.sel) - 1),
               NextState("ACT"),
            )
        )
        fsm.act("ACT",
            wishbone.stb.eq(1),
            wishbone.cyc.eq(1),
            If(wishbone.ack,
                If(~wishbone.we,
                    NextValue(ahb.rdata, wishbone.dat_r)
                ),
                NextState("IDLE")
            )
        )
