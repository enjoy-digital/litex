#
# This file is part of LiteX.
#
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from litex.build.generic_platform import GenericPlatform
from litex.build.openfpga import common, openfpga

# OpenFPGAPlatform -------------------------------------------------------------------------------

class OpenFPGAPlatform(GenericPlatform):
    def __init__(self, device, *args, **kwargs):
        GenericPlatform.__init__(self, device, *args, **kwargs)
        self.toolchain = openfpga.OpenFPGAToolchain()

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict(common.openfpga_special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args,
            special_overrides = so,
            attr_translate    = self.toolchain.attr_translate,
            **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)
