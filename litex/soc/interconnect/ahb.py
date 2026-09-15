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
        if addressing != "byte":
            raise ValueError("AHB only supports byte addressing.")
        if mode not in ["rw", "r", "w"]:
            raise ValueError("Unsupported AHB mode: {}.".format(mode))
        Record.__init__(self, ahb_description(data_width, address_width))
        self.data_width    = data_width
        self.address_width = address_width
        self.addressing    = addressing
        self.mode          = mode

# AHB to Wishbone  ---------------------------------------------------------------------------------

class AHB2Wishbone(LiteXModule):
    """
    This module converts AHB protocol transactions to the Wishbone protocol.

    With ``with_bursting``, full-width AHB bursts produce Wishbone CTI/BTE and consecutive
    beats can complete without an extra address-phase cycle. Subword transfers remain classic
    Wishbone accesses. The default retains the registered response path.
    """
    def __init__(self, ahb, wishbone, with_bursting=False):
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

        if with_bursting:
            assert wishbone.addressing == "word"
            self._init_bursting(ahb, wishbone, wishbone_sel_decoder(ahb.size, ahb.addr), wishbone_adr_shift)
            return

        # Second cycle of the two-cycle AHB ERROR response (signaled while back in ADDRESS-PHASE so
        # that the next Transfer can be accepted in the same cycle, as the AHB pipeline requires).
        ahb_error_resp = Signal()

        # FSM.
        self.fsm = fsm = FSM()
        fsm.act("ADDRESS-PHASE",
            ahb.readyout.eq(1),
            ahb.resp.eq(ahb_error_resp),
            NextValue(ahb_error_resp, 0),
            # Accept both NONSEQUENTIAL and SEQUENTIAL Transfers: each AHB beat carries its full
            # address, so burst beats can be converted as independent Wishbone accesses (SEQUENTIAL
            # beats were previously OKAY-ed without generating an access: silent data loss).
            If(ahb.sel & ahb.trans[1],
                # Respond with an AHB ERROR to unsupported Transfer sizes (previously silently
                # OKAY-ed without generating an access).
                If(ahb.size > log2_int(ahb.data_width//8),
                    NextState("ERROR-RESPONSE")
                ).Else(
                    NextValue(wishbone.adr, ahb.addr[wishbone_adr_shift:]),
                    NextValue(wishbone.we,  ahb.write),
                    NextValue(wishbone.sel, wishbone_sel_decoder(ahb.size, ahb.addr)),
                    NextState("DATA-PHASE"),
                )
            )
        )
        fsm.act("DATA-PHASE",
            wishbone.stb.eq(1),
            wishbone.cyc.eq(1),
            wishbone.dat_w.eq(ahb.wdata),
            # On Wishbone Error, respond with an AHB ERROR (a Wishbone err, with or without ack,
            # was previously reported as OKAY since resp was only driven while readyout was low).
            If(wishbone.err,
                NextState("ERROR-RESPONSE")
            ).Elif(wishbone.ack,
                NextValue(ahb.rdata, wishbone.dat_r),
                NextState("ADDRESS-PHASE")
            )
        )
        fsm.act("ERROR-RESPONSE",
            # First cycle of the two-cycle AHB ERROR response (readyout low); the second cycle
            # (readyout high) is signaled in ADDRESS-PHASE through ahb_error_resp.
            ahb.resp.eq(1),
            NextValue(ahb_error_resp, 1),
            NextState("ADDRESS-PHASE"),
        )

    def _init_bursting(self, ahb, wishbone, select, address_shift):
        from litex.soc.interconnect.wishbone import (
            CTI_BURST_NONE, CTI_BURST_INCREMENTING, CTI_BURST_END)

        # Keep full-width AHB bursts in one Wishbone cycle. A narrow LiteDRAM frontend can then
        # combine writes and share a native read among the beats of a cache line.
        beats_left = Signal(5)
        next_cti   = Signal(3)
        hold_cycle = Signal()
        self.comb += [
            wishbone.dat_w.eq(ahb.wdata),
            ahb.rdata.eq(wishbone.dat_r),
            next_cti.eq(CTI_BURST_NONE),
            If((ahb.size == log2_int(ahb.data_width//8)) & (ahb.burst != 0),
                next_cti.eq(CTI_BURST_INCREMENTING),
                If((ahb.burst != 1) & (ahb.trans == AHBTransferType.SEQUENTIAL) & (beats_left == 1),
                    next_cti.eq(CTI_BURST_END),
                ),
            ),
        ]

        def accept_transfer():
            return If(ahb.sel & ahb.trans[1],
                If(ahb.size > log2_int(ahb.data_width//8),
                    NextValue(hold_cycle, 0),
                    NextState("ERROR-RESPONSE"),
                ).Else(
                    NextValue(wishbone.adr, ahb.addr[address_shift:]),
                    NextValue(wishbone.we,  ahb.write),
                    NextValue(wishbone.sel, select),
                    NextValue(wishbone.cti, next_cti),
                    # AHB WRAP4/8/16 encodings map directly to Wishbone BTE; INCR is linear.
                    NextValue(wishbone.bte, Mux(ahb.burst[0], 0, ahb.burst[1:3])),
                    NextValue(hold_cycle, next_cti == CTI_BURST_INCREMENTING),
                    If(ahb.trans == AHBTransferType.NONSEQUENTIAL,
                        Case(ahb.burst[1:3], {
                            index: NextValue(beats_left, (1 << (index + 1)) - 1)
                            for index in range(4)
                        }),
                    ).Else(
                        NextValue(beats_left, beats_left - 1),
                    ),
                    If(hold_cycle & (ahb.trans == AHBTransferType.NONSEQUENTIAL),
                        # A new NONSEQ may terminate an INCR or an incomplete fixed-length burst.
                        # Drop CYC before its first beat so buffered frontends observe the boundary.
                        NextState("BURST-END"),
                    ).Else(
                        NextState("DATA-PHASE"),
                    ),
                )
            ).Else(
                # BUSY pauses the address stream without ending the current burst.
                If(ahb.trans != AHBTransferType.BUSY, NextValue(hold_cycle, 0)),
                NextState("ADDRESS-PHASE"),
            )

        self.fsm = fsm = FSM(reset_state="ADDRESS-PHASE")
        fsm.act("ADDRESS-PHASE",
            ahb.readyout.eq(1),
            wishbone.cyc.eq(hold_cycle),
            accept_transfer(),
        )
        fsm.act("DATA-PHASE",
            wishbone.cyc.eq(1),
            wishbone.stb.eq(1),
            If(wishbone.err,
                ahb.resp.eq(1),
                NextValue(hold_cycle, 0),
                NextState("ERROR-LAST"),
            ).Elif(wishbone.ack,
                # Complete this data phase and accept the next address in the same cycle.
                ahb.readyout.eq(1),
                accept_transfer(),
            ),
        )
        fsm.act("BURST-END",
            NextState("DATA-PHASE"),
        )
        fsm.act("ERROR-RESPONSE",
            ahb.resp.eq(1),
            NextState("ERROR-LAST"),
        )
        fsm.act("ERROR-LAST",
            ahb.resp.eq(1),
            ahb.readyout.eq(1),
            accept_transfer(),
        )
