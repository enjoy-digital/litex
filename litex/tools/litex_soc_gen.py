#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""
LiteX standalone SoC generator.

This generator reduces the scope of LiteX to CPU/Peripherals selection/integration and to the creation
of SoC with MMAP/Streaming DMA interfaces that can be reintegrated in external designs (or LiteX SoC).
Think of it as a mini Nios SOPC Builder/ Zynq or Microblaze Subsystem generator that offers you the
possibility to reuse any of CPU supported by LiteX :)
"""

import argparse

from migen import *

from litex.build.generic_platform import *

from litex.soc.integration.soc_core import *
from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.builder import *
from litex.soc.interconnect import wishbone
from litex.soc.interconnect import axi

# IOs/Interfaces -----------------------------------------------------------------------------------

def get_common_ios():
    return [
        # Clk/Rst.
        ("clk", 0, Pins(1)),
        ("rst", 0, Pins(1)),
    ]

def get_uart_ios():
    return [
        # Serial
        ("uart", 0,
            Subsignal("tx",  Pins(1)),
            Subsignal("rx", Pins(1)),
        )
    ]

# Platform -----------------------------------------------------------------------------------------

class Platform(GenericPlatform):
    def build(self, fragment, build_dir, build_name, **kwargs):
        os.makedirs(build_dir, exist_ok=True)
        os.chdir(build_dir)
        conv_output = self.get_verilog(fragment, name=build_name)
        conv_output.write(f"{build_name}.v")

# LiteX SoC Generator ------------------------------------------------------------------------------

class LiteXSoCGenerator(SoCMini):
    def __init__(self, name="litex_soc", sys_clk_freq=int(50e6), **kwargs):
        # Platform ---------------------------------------------------------------------------------
        platform = Platform(device="", io=get_common_ios())
        platform.name = name
        platform.add_extension(get_uart_ios())

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = CRG(
            clk = platform.request("clk"),
            rst = platform.request("rst"),
        )

        # SoC --------------------------------------------------------------------------------------
        if kwargs["uart_name"] == "serial":
            kwargs["uart_name"] = "uart"
        SoCCore.__init__(self, platform, clk_freq=sys_clk_freq, **kwargs)

        # MMAP Slave Interface ---------------------------------------------------------------------
        s_bus = {
            "wishbone" : wishbone.Interface(),
            "axi-lite" : axi.AXILiteInterface(),

        }[kwargs["bus_standard"]]
        self.bus.add_master(name="mmap_s", master=s_bus)
        platform.add_extension(s_bus.get_ios("mmap_s"))
        wb_pads = platform.request("mmap_s")
        self.comb += s_bus.connect_to_pads(wb_pads, mode="slave")

        # MMAP Master Interface --------------------------------------------------------------------
        # FIXME: Allow Region configuration.
        m_bus = {
            "wishbone" : wishbone.Interface(),
            "axi-lite" : axi.AXILiteInterface(),

        }[kwargs["bus_standard"]]
        wb_region = SoCRegion(origin=0x2000_0000, size=0x1000_0000, cached=True) # FIXME.
        self.bus.add_slave(name="mmap_m", slave=m_bus, region=wb_region)
        platform.add_extension(m_bus.get_ios("mmap_m"))
        wb_pads = platform.request("mmap_m")
        self.comb += m_bus.connect_to_pads(wb_pads, mode="master")

# Build --------------------------------------------------------------------------------------------
def main():
    # Arguments.
    from litex.soc.integration.soc import LiteXSoCArgumentParser
    parser = LiteXSoCArgumentParser(description="LiteX standalone SoC generator")
    target_group = parser.add_argument_group(title="Generator options")
    target_group.add_argument("--name",          default="litex_soc", help="SoC Name.")
    target_group.add_argument("--build",         action="store_true", help="Build SoC.")
    target_group.add_argument("--sys-clk-freq",  default=int(50e6),   help="System clock frequency.")
    builder_args(parser)
    soc_core_args(parser)
    args = parser.parse_args()

    # SoC.
    soc = LiteXSoCGenerator(
        name         = args.name,
        sys_clk_freq = int(float(args.sys_clk_freq)),
        **soc_core_argdict(args)
    )

    # Build.
    builder = Builder(soc, **builder_argdict(args))
    builder.build(build_name=args.name, run=args.build)

if __name__ == "__main__":
    main()
