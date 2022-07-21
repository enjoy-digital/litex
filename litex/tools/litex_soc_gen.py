#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2022 Joseph Wagane Faye <joseph-wagane.faye@insa-rennes.fr>
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

def get_debug_ios(debug_width=8):
    return [
        ("debug", 0, Pins(debug_width)),
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
    def __init__(self, name="litex_soc", sys_clk_freq=int(50e6), n_mi=3, n_si=0, **kwargs):
        assert (n_mi + n_si) < 5
        self.kwargs = kwargs

        # Platform ---------------------------------------------------------------------------------
        self.platform = Platform(device="", io=get_common_ios())
        self.platform.name = name
        self.platform.add_extension(get_uart_ios())

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = CRG(
            clk = self.platform.request("clk"),
            rst = self.platform.request("rst"),
        )

        # SoC --------------------------------------------------------------------------------------
        if self.kwargs["uart_name"] == "serial":
            self.kwargs["uart_name"] = "uart"
        SoCCore.__init__(self, self.platform, clk_freq=sys_clk_freq, ident=f"LiteX standalone SoC - {name}", **kwargs)

        for n in range(n_mi):
            origins=[0xa000_0000, 0xb000_0000, 0xc000_0000, 0xd000_0000]
            self.add_master_interface(mmap_id=n, origin=origins[n])

        for n in range(n_si):
            self.add_slave_interface(n)

        # Debug ------------------------------------------------------------------------------------
        self.platform.add_extension(get_debug_ios())
        debug_pads = self.platform.request("debug")
        self.comb += [
            # Export Signal(s) for debug.
            debug_pads[0].eq(0), # 0.
            debug_pads[1].eq(1), # 1.
            # Etc...
        ]
    def add_slave_interface(self, mmap_id):
        assert isinstance(mmap_id, int)
        # MMAP Slave Interface ---------------------------------------------------------------------
        s_bus = {
            "wishbone": wishbone.Interface(),
            "axi-lite": axi.AXILiteInterface(),
        }[self.kwargs["bus_standard"]]
        self.bus.add_master(name="mmap_s_{}".format(mmap_id), master=s_bus)
        self.platform.add_extension(s_bus.get_ios("mmap_s_{}".format(mmap_id)))
        wb_pads = self.platform.request("mmap_s_{}".format(mmap_id))
        self.comb += s_bus.connect_to_pads(wb_pads, mode="slave")

    def add_master_interface(self, mmap_id, origin=0xa0000000):
        assert isinstance(mmap_id, int)
        # MMAP Master Interface --------------------------------------------------------------------
        m_bus = {
            "wishbone": wishbone.Interface(),
            "axi-lite": axi.AXILiteInterface(),
        }[self.kwargs["bus_standard"]]
        wb_region = SoCRegion(origin=origin, size=0x10000000, cached=False)
        self.bus.add_slave(name="mmap_m_{}".format(mmap_id), slave=m_bus, region=wb_region)
        self.platform.add_extension(m_bus.get_ios("mmap_m_{}".format(mmap_id)))
        wb_pads = self.platform.request("mmap_m_{}".format(mmap_id))
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
    target_group.add_argument("--n-master-inter",  default=int(2),   help="Number of master interfaces")
    target_group.add_argument("--n-slave-inter",  default=int(0),   help="Number of slave interfaces.")

    builder_args(parser)
    soc_core_args(parser)
    args = parser.parse_args()
    print("Argument dict {}".format(args))
    # SoC.
    soc = LiteXSoCGenerator(
        name         = args.name,
        sys_clk_freq = int(float(args.sys_clk_freq)),
        n_mi = int(args.n_master_inter),
        n_si = int(args.n_slave_inter),
        **soc_core_argdict(args)
    )
    # Build.
    builder = Builder(soc, **builder_argdict(args))
    builder.build(build_name=args.name, run=args.build)

if __name__ == "__main__":
    main()
