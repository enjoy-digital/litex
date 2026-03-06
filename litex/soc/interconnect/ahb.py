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
    def __init__(self, data_width=32, address_width=32, addressing="byte", mode="rw"):
        assert addressing == "byte"
        Record.__init__(self, ahb_description(data_width, address_width))
        self.data_width    = data_width
        self.address_width = address_width
        self.addressing    = addressing
        assert mode in ["rw", "r", "w"]
        self.mode          = mode

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
        assert ahb.data_width in [32, 64]
        assert ahb.data_width     == wishbone.data_width
        assert ahb.address_width  == wishbone.adr_width + wishbone_adr_shift

        def wishbone_sel_decoder(ahb_size, ahb_addr):
            if ahb.data_width == 64:
                wishbone_sel = Signal(8)
                self.comb += Case(ahb_size, {
                    # 8-bit access.
                    0b00 : Case(ahb_addr[0:3], {
                        0b000 : wishbone_sel.eq(0b0000_0001),
                        0b001 : wishbone_sel.eq(0b0000_0010),
                        0b010 : wishbone_sel.eq(0b0000_0100),
                        0b011 : wishbone_sel.eq(0b0000_1000),
                        0b100 : wishbone_sel.eq(0b0001_0000),
                        0b101 : wishbone_sel.eq(0b0010_0000),
                        0b110 : wishbone_sel.eq(0b0100_0000),
                        0b111 : wishbone_sel.eq(0b1000_0000),
                    }),
                    # 16-bit access.
                    0b01 : Case(ahb_addr[1:3], {
                        0b00 : wishbone_sel.eq(0b0000_0011),
                        0b01 : wishbone_sel.eq(0b0000_1100),
                        0b10 : wishbone_sel.eq(0b0011_0000),
                        0b11 : wishbone_sel.eq(0b1100_0000),
                    }),
                    # 32-bit access.
                    0b10 : Case(ahb_addr[2:3], {
                        0b0 : wishbone_sel.eq(0b0000_1111),
                        0b1 : wishbone_sel.eq(0b1111_0000),
                    }),
                    # 64-bit access.
                    0b11 : wishbone_sel.eq(0b1111_1111),
                })
                return wishbone_sel
            if ahb.data_width == 32:
                wishbone_sel = Signal(4)
                self.comb += Case(ahb_size, {
                    # 8-bit access.
                    0b00 : Case(ahb_addr[0:2], {
                        0b00 : wishbone_sel.eq(0b0001),
                        0b01 : wishbone_sel.eq(0b0010),
                        0b10 : wishbone_sel.eq(0b0100),
                        0b11 : wishbone_sel.eq(0b1000),
                    }),
                    # 16-bit access.
                    0b01 : Case(ahb_addr[1:2], {
                        0b0 : wishbone_sel.eq(0b0011),
                        0b1 : wishbone_sel.eq(0b1100),
                    }),
                    # 32-bit access.
                    0b10 : wishbone_sel.eq(0b1111),
                    # 64-bit access (Should not happen but do a full 32-bit access).
                    0b11 : wishbone_sel.eq(0b1111),
                })
                return wishbone_sel

        # FSM.
        self.fsm = fsm = FSM()
        fsm.act("ADDRESS-PHASE",
            ahb.readyout.eq(1),
            If(ahb.sel &
              (ahb.size  <= log2_int(ahb.data_width//8)) &
              (ahb.trans == AHBTransferType.NONSEQUENTIAL),
                NextValue(wishbone.adr, ahb.addr[wishbone_adr_shift:]),
                NextValue(wishbone.we,  ahb.write),
                NextValue(wishbone.sel, wishbone_sel_decoder(ahb.size, ahb.addr)),
                NextState("DATA-PHASE"),
            )
        )
        fsm.act("DATA-PHASE",
            wishbone.stb.eq(1),
            wishbone.cyc.eq(1),
            wishbone.dat_w.eq(ahb.wdata),
            ahb.resp.eq(wishbone.err),
            If(wishbone.ack,
                NextValue(ahb.rdata, wishbone.dat_r),
                NextState("ADDRESS-PHASE")
            )
        )
