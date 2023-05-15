#
# This file is part of LiteX.
#
# Copyright (c) 2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from litex.build.generic_platform import GenericPlatform
from litex.build.quicklogic import common, f4pga

# QuickLogicPlatform -------------------------------------------------------------------------------

class QuickLogicPlatform(GenericPlatform):
    _bitstream_ext = ".bit"

    _supported_toolchains = ["f4pga"]

    def __init__(self, *args, toolchain="f4pga", **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)
        if toolchain == "symbiflow" or toolchain == "f4pga":
            self.toolchain = f4pga.F4PGAToolchain()
        else:
            raise ValueError(f"Unknown toolchain {toolchain}")

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict(common.quicklogic_special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args,
            special_overrides = so,
            attr_translate    = self.toolchain.attr_translate,
            **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)
