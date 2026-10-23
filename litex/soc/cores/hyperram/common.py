#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""HyperRAM controller common definitions (timings, PHY interface)."""

from migen import *

# Constants ----------------------------------------------------------------------------------------

HYPERRAM_TRWR   = 40e-9  # Read-Write recovery time (s).
HYPERRAM_TCSM   = 4e-6   # Max CS# low time (s).
HYPERRAM_TVCS   = 150e-6 # Power-up/reset to first access (s).

# PHY Interface ------------------------------------------------------------------------------------

class HyperRAMPHYInterface:
    """Signals between HyperRAMCore and a HyperRAM PHY (DDR IO registers).

    Core clock domain (one cycle = one CK period):
    - cs_n, rst_n, ck_en         : CK toggles (rising then falling edge) during cycles with ck_en.
    - dq_o_hi/lo, dq_oe          : DQ for first (rising CK) / second (falling CK) edge.
    - rwds_o_hi/lo, rwds_oe      : RWDS (write mask) for first / second edge.
    Capture clock domain (`cd_cap`):
    - dq_i_hi/lo, rwds_i_hi/lo   : DDR captured inputs (HI = first half-word in time).
    """
    def __init__(self, dq_width=16, cd_cap="hyperram_cap"):
        self.dq_width = dq_width
        self.cd_cap   = cd_cap
        rwds_width    = dq_width//8
        self.cs_n      = Signal(reset=1)
        self.rst_n     = Signal(reset=1)
        self.ck_en     = Signal()
        self.dq_o_hi   = Signal(dq_width)
        self.dq_o_lo   = Signal(dq_width)
        self.dq_oe     = Signal()
        self.rwds_o_hi = Signal(rwds_width)
        self.rwds_o_lo = Signal(rwds_width)
        self.rwds_oe   = Signal()
        self.dq_i_hi   = Signal(dq_width)
        self.dq_i_lo   = Signal(dq_width)
        self.rwds_i_hi = Signal(rwds_width)
        self.rwds_i_lo = Signal(rwds_width)
