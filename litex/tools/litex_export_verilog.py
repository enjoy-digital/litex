#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2023 Josuah Demangeon <me@josuah.net>
# SPDX-License-Identifier: BSD-2-Clause

import sys
import argparse

from migen import *

from litex.gen import *
from litex.build.io import *
from litex.soc.cores.clock import *
from litex.soc.cores.bitbang import I2CMaster
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.build.generic_platform import Pins, Subsignal
from litex.build.export.platform import ExportPlatform

# IOs ----------------------------------------------------------------------------------------------

_io = [
    # Clk / Rst.
    ("sys_clk", 0, Pins(1)),
    ("sys_rst", 0, Pins(1)),

    # Serial.
    ("serial", 0,
        Subsignal("tx", Pins(1)),
        Subsignal("rx", Pins(1)),
    ),

    # Ethernet (Stream Endpoint).
    ("eth_clocks", 0,
        Subsignal("tx", Pins(1)),
        Subsignal("rx", Pins(1)),
    ),
    ("eth", 0,
        Subsignal("source_valid", Pins(1)),
        Subsignal("source_ready", Pins(1)),
        Subsignal("source_data",  Pins(8)),

        Subsignal("sink_valid",   Pins(1)),
        Subsignal("sink_ready",   Pins(1)),
        Subsignal("sink_data",    Pins(8)),
    ),

    # Ethernet (XGMII).
    ("xgmii_eth", 0,
        Subsignal("rx_data",      Pins(64)),
        Subsignal("rx_ctl",       Pins(8)),
        Subsignal("tx_data",      Pins(64)),
        Subsignal("tx_ctl",       Pins(8)),
    ),

    # Ethernet (GMII).
    ("gmii_eth", 0,
        Subsignal("rx_data",      Pins(8)),
        Subsignal("rx_dv",        Pins(1)),
        Subsignal("rx_er",        Pins(1)),
        Subsignal("tx_data",      Pins(8)),
        Subsignal("tx_en",        Pins(1)),
        Subsignal("tx_er",        Pins(1)),
    ),

    # I2C.
    ("i2c", 0,
        Subsignal("scl",     Pins(1)),
        Subsignal("sda",     Pins(1)),
    ),

    # SPI-Flash (X1).
    ("spiflash", 0,
        Subsignal("cs_n", Pins(1)),
        Subsignal("clk",  Pins(1)),
        Subsignal("mosi", Pins(1)),
        Subsignal("miso", Pins(1)),
        Subsignal("wp",   Pins(1)),
        Subsignal("hold", Pins(1)),
    ),

    # SPI-Flash (X4).
    ("spiflash4x", 0,
        Subsignal("cs_n", Pins(1)),
        Subsignal("clk",  Pins(1)),
        Subsignal("dq",   Pins(4)),
    ),

    # Tristate GPIOs (for sim control/status).
    ("gpio", 0,
        Subsignal("oe", Pins(32)),
        Subsignal("o",  Pins(32)),
        Subsignal("i",  Pins(32)),
    ),

    # Video (VGA).
    ("vga", 0,
        Subsignal("hsync", Pins(1)),
        Subsignal("vsync", Pins(1)),
        Subsignal("de",    Pins(1)),
        Subsignal("r",     Pins(8)),
        Subsignal("g",     Pins(8)),
        Subsignal("b",     Pins(8)),
    )
]

# Platform -----------------------------------------------------------------------------------------

class Platform(ExportPlatform):
    def __init__(self):
        ExportPlatform.__init__(self, "export", _io)

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    def __init__(self, sys_clk_freq=48e6,
        with_i2c        = False,
        with_spi_flash  = False,
        spi_flash_part  = None,
        spi_flash_io    = None,
        **kwargs):
        platform = Platform()

        # CRG --------------------------------------------------------------------------------------
        self.crg = CRG(platform.request("sys_clk"))

        # SoCCore ----------------------------------------------------------------------------------
        SoCCore.__init__(self, platform, sys_clk_freq, ident="LiteX SoC Verilog export", **kwargs)

        if with_i2c:
            self.i2c = I2CMaster(platform.request("i2c", 0))

        if with_spi_flash:
            from litespi.opcodes import SpiNorFlashOpCodes as Codes
            from litespi import modules
            spiflash_module = getattr(modules, spi_flash_part)(Codes.READ_1_1_4)
            self.add_spi_flash(mode="4x", module=spiflash_module, with_master=True)

# Build --------------------------------------------------------------------------------------------

def main():
    from litex.build.parser import LiteXArgumentParser
    parser = LiteXArgumentParser(platform=Platform, description="LiteX SoC Verilog export.")
    parser.add_target_argument("--sys-clk-freq", default=48e6, type=float, help="System clock frequency.")
    parser.add_target_argument("--with-i2c", action="store_true", help="Enable I2C.")
    parser.add_target_argument("--with-spi-flash", action="store_true", help="Enable SPI flash (MMAPed).")
    parser.add_target_argument("--spi-flash-part", default="S25FL128L", help="Part name for the SPI flash.")
    parser.add_target_argument("--spi-flash-io", default="1_1_4", help="SPI flash selected I/O mode.")
    args = parser.parse_args()

    soc = BaseSoC(
        sys_clk_freq   = args.sys_clk_freq,
        with_i2c       = args.with_i2c,
        with_spi_flash = args.with_spi_flash,
        spi_flash_part = args.spi_flash_part,
        spi_flash_io   = args.spi_flash_io,
        **parser.soc_argdict
    )
    builder = Builder(soc, **parser.builder_argdict)
    builder.build(**parser.toolchain_argdict)

if __name__ == "__main__":
    main()
