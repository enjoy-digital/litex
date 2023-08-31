#
# This file is part of LiteX.
#
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from litex.build.generic_platform import GenericPlatform
from litex.build.osfpga import common, osfpga

# OSFPGAPlatform -----------------------------------------------------------------------------------

class OSFPGAPlatform(GenericPlatform):
    _bitstream_ext = ".bin"

    _supported_toolchains = ["osfpga"]

    def __init__(self, device, *args, toolchain="foedag", devicename=None, **kwargs):
        GenericPlatform.__init__(self, device, *args, **kwargs)
        self.devicename = devicename
        if toolchain in ["foedag", "raptor"]:
            self.toolchain = osfpga.OSFPGAToolchain(toolchain=toolchain)
        else:
            raise ValueError(f"Unknown toolchain {toolchain}")

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict(common.osfpga_special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args,
            special_overrides = so,
            attr_translate    = self.toolchain.attr_translate,
            **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

    def add_false_path_constraint(self, from_, to):
        pass # FIXME: Implement.
