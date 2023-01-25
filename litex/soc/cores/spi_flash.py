#
# This file is part of LiteX.
#
# Copyright (c) 2014-2023 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import LiteXModule

from litex.soc.interconnect.csr import *
from litex.soc.cores.spi import SPIMaster

# Xilinx 7-Series FPGAs SPI Flash (non-memory-mapped) ----------------------------------------------

class S7SPIFlash(LiteXModule):
    def __init__(self, pads, sys_clk_freq, spi_clk_freq=25e6):
        self.spi = spi = SPIMaster(None, 40, sys_clk_freq, spi_clk_freq)
        self.specials += Instance("STARTUPE2",
            i_CLK       = 0,
            i_GSR       = 0,
            i_GTS       = 0,
            i_KEYCLEARB = 0,
            i_PACK      = 0,
            i_USRCCLKO  = spi.pads.clk,
            i_USRCCLKTS = 0,
            i_USRDONEO  = 1,
            i_USRDONETS = 1,
        )
        if hasattr(pads, "vpp"):
            pads.vpp.reset = 1
        if hasattr(pads, "hold"):
            pads.hold.reset = 1
        if hasattr(pads, "cs_n"):
            self.comb += pads.cs_n.eq(spi.pads.cs_n)
        self.comb += [
            pads.mosi.eq(spi.pads.mosi),
            spi.pads.miso.eq(pads.miso)
        ]

# Xilinx Ultrascale FPGAs SPI Flash (non-memory-mapped) --------------------------------------------

class USSPIFlash(LiteXModule):
    def __init__(self, sys_clk_freq, spi_clk_freq=25e6):
        self.spi = spi = SPIMaster(None, 40, sys_clk_freq, spi_clk_freq)
        spi_dts = Signal(4)
        spi_do  = Signal(4)
        spi_di  = Signal(4)
        self.comb += [
            # D0: MOSI (Output).
            spi_dts[0].eq(0),
            spi_do[0].eq(spi.pads.mosi),
            # D1: MISO (Input).
            spi_dts[1].eq(1),
            spi.pads.miso.eq(spi_di[1]),
            # D2: Vpp (Output).
            spi_dts[2].eq(0),
            spi_do[2].eq(1),
            # D3: Hold (Input).
            spi_dts[3].eq(0),
            spi_do[3].eq(1),
        ]
        self.specials += Instance("STARTUPE3",
            i_GSR       = 0,
            i_GTS       = 0,
            i_KEYCLEARB = 0,
            i_PACK      = 0,
            i_USRCCLKO  = spi.pads.clk,
            i_USRCCLKTS = 0,
            i_USRDONEO  = 1,
            i_USRDONETS = 1,
            i_FCSBTS    = 0,
            i_FCSBO     = spi.pads.cs_n,
            i_DTS       = spi_dts,
            i_DO        = spi_do,
            o_DI        = spi_di,
        )

# Lattice ECP5 FPGAs SPI Flash (non-memory-mapped) -------------------------------------------------

class ECP5SPIFlash(Module, AutoCSR):
    def __init__(self, pads, sys_clk_freq, spi_clk_freq=25e6):
        self.submodules.spi = spi = SPIMaster(None, 40, sys_clk_freq, spi_clk_freq)
        self.specials += Instance("USRMCLK",
            i_USRMCLKI  = spi.pads.clk,
            i_USRMCLKTS = 0
        )
        if hasattr(pads, "vpp"):
            pads.vpp.reset = 1
        if hasattr(pads, "hold"):
            pads.hold.reset = 1
        if hasattr(pads, "cs_n"):
            self.comb += pads.cs_n.eq(spi.pads.cs_n)
        self.comb += [
            pads.mosi.eq(spi.pads.mosi),
            spi.pads.miso.eq(pads.miso)
        ]
