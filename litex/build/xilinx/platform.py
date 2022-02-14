#
# This file is part of LiteX.
#
# Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2022 Victor Suarez Rovere <suarezvictor@gmai.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

from litex.build.generic_platform import GenericPlatform
from litex.build.xilinx import common

# XilinxPlatform -----------------------------------------------------------------------------------

class XilinxPlatform(GenericPlatform):
    bitstream_ext = ".bit"

    def __init__(self, *args, toolchain="ise", **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)
        self.edifs = set()
        self.ips   = {}
        if toolchain == "ise":
            from litex.build.xilinx import ise
            self.toolchain = ise.XilinxISEToolchain()
        elif toolchain == "vivado":
            from litex.build.xilinx import vivado
            self.toolchain = vivado.XilinxVivadoToolchain()
        elif toolchain == "symbiflow":
            from litex.build.xilinx import symbiflow
            self.toolchain = symbiflow.SymbiflowToolchain()
        elif toolchain == "yosys+nextpnr":
            from litex.build.xilinx import yosys_nextpnr
            self.toolchain = yosys_nextpnr.YosysNextpnrToolchain()
        else:
            raise ValueError(f"Unknown toolchain {toolchain}")

    def add_edif(self, filename):
        self.edifs.add((os.path.abspath(filename)))

    def add_ip(self, filename, disable_constraints=False):
        self.ips.update({os.path.abspath(filename): disable_constraints})

    def add_platform_command(self, command, **signals):
        skip = False
        from litex.build.xilinx import yosys_nextpnr
        if isinstance(self.toolchain, yosys_nextpnr.YosysNextpnrToolchain):
            # FIXME: Add support for INTERNAL_VREF to yosys+nextpnr flow.
            if "set_property INTERNAL_VREF" in command:
                print("WARNING: INTERNAL_VREF constraint removed since not yet supported by yosys-nextpnr flow.")
                skip = True
        if not skip:
            GenericPlatform.add_platform_command(self, command, **signals)

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict(common.xilinx_special_overrides)
        if self.device[:3] == "xc6":
            so.update(common.xilinx_s6_special_overrides)
        if self.device[:3] == "xc7":
            so.update(common.xilinx_s7_special_overrides)
        if self.device[:4] == "xcku":
            so.update(common.xilinx_us_special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args,
            special_overrides = so,
            attr_translate    = self.toolchain.attr_translate,
            **kwargs)

    def get_edif(self, fragment, **kwargs):
        return GenericPlatform.get_edif(self, fragment, "UNISIMS", "Xilinx", self.device, **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

    def add_period_constraint(self, clk, period):
        if clk is None: return
        if hasattr(clk, "p"):
            clk = clk.p
        self.toolchain.add_period_constraint(self, clk, period)

    def add_false_path_constraint(self, from_, to):
        if hasattr(from_, "p"):
            from_ = from_.p
        if hasattr(to, "p"):
            to = to.p
        self.toolchain.add_false_path_constraint(self, from_, to)
