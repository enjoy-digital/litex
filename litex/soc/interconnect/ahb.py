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

class AHBTransferType(IntEnum):
    """Defines types of AHB transfers."""
    IDLE          = 0
    BUSY          = 1
    NONSEQUENTIAL = 2
    SEQUENTIAL    = 3

# AHB Definition -----------------------------------------------------------------------------------

def ahb_description(data_width, address_width):
    return [
        ("addr",     address_width, DIR_M_TO_S),
        ("burst",                3, DIR_M_TO_S),
        ("mastlock",             1, DIR_M_TO_S),
        ("prot",                 4, DIR_M_TO_S),
        ("size",                 3, DIR_M_TO_S),
        ("trans",                2, DIR_M_TO_S),
        ("wdata",       data_width, DIR_M_TO_S),
        ("write",                1, DIR_M_TO_S),
        ("sel",                  1, DIR_M_TO_S),
        ("rdata",       data_width, DIR_S_TO_M),
        ("readyout",             1, DIR_S_TO_M),
        ("resp",                 1, DIR_S_TO_M),
]

class AHBInterface(Record):
    def __init__(self, data_width=32, address_width=32):
        Record.__init__(self, ahb_description(data_width, address_width))
        self.data_width    = data_width
        self.address_width = address_width
        self.addressing    = "byte"

# AHB to Wishbone  ---------------------------------------------------------------------------------

class AHB2Wishbone(LiteXModule):
    """
    This module converts AHB protocol transactions to the Wishbone protocol.

    It takes as input an AHB interface and a Wishbone interface and does the conversion.
    """
    def __init__(self, ahb, wishbone):
        # Parameters/Checks.
        wishbone_adr_shift = {
            "word" : log2_int(ahb.data_width//8),
            "byte" : 0
        }[wishbone.addressing]
        assert ahb.data_width     == wishbone.data_width
        assert ahb.address_width  == wishbone.adr_width + wishbone_adr_shift

        # FSM.
        self.fsm = fsm = FSM()
        fsm.act("ADDRESS-PHASE",
            ahb.readyout.eq(1),
            If(ahb.sel &
              (ahb.size  <= log2_int(ahb.data_width//8)) &
              (ahb.trans == AHBTransferType.NONSEQUENTIAL),
               NextValue(wishbone.adr, ahb.addr[wishbone_adr_shift:]),
               NextValue(wishbone.we,  ahb.write),
               NextState("DATA-PHASE"),
            )
        )
        fsm.act("DATA-PHASE",
            wishbone.stb.eq(1),
            wishbone.cyc.eq(1),
            wishbone.dat_w.eq(ahb.wdata),
            wishbone.sel.eq(2**len(wishbone.sel) - 1),
            ahb.resp.eq(wishbone.err),
            If(wishbone.ack,
                NextValue(ahb.rdata, wishbone.dat_r),
                NextState("ADDRESS-PHASE")
            )
        )
