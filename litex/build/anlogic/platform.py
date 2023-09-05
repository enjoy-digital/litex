#
# This file is part of LiteX.
#
# Copyright (c) 2021 Miodrag Milanovic <mmicko@gmail.com>
# Copyright (c) 2015-2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from litex.build.generic_platform import GenericPlatform
from litex.build.anlogic import common, anlogic

# AnlogicPlatform ----------------------------------------------------------------------------------

class AnlogicPlatform(GenericPlatform):
    _bitstream_ext = ".bit"

    _supported_toolchains = ["td"]

    def __init__(self, device, *args, toolchain="td", **kwargs):
        GenericPlatform.__init__(self, device, *args, **kwargs)
        if toolchain == "td":
            self.toolchain = anlogic.TangDinastyToolchain()
        else:
            raise ValueError(f"Unknown toolchain {toolchain}")

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict(common.anlogic_special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args,
            special_overrides = so,
            attr_translate    = self.toolchain.attr_translate,
            **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)
