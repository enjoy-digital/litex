#
# This file is part of LiteX.
#
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.generic_platform import GenericPlatform
from litex.build.microsemi import common, libero_soc

# MicrosemiPlatform --------------------------------------------------------------------------------

class MicrosemiPlatform(GenericPlatform):
    _bitstream_ext = ".bit"
    _jtag_support  = False

    _supported_toolchains = ["libero_soc"]

    def __init__(self, *args, toolchain="libero_soc", **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)
        if toolchain == "libero_soc":
            self.toolchain = libero_soc.MicrosemiLiberoSoCToolchain()
        else:
            raise ValueError(f"Unknown toolchain {toolchain}")

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        # ProASIC3 family does not support register init in Verilog.
        if self.toolchain.family is None:
            self.toolchain.finalize()
        if self.toolchain.family.startswith("ProASIC3"):
            kwargs["regs_init"] = False
        so = dict()
        so.update(self.toolchain.special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args,
            special_overrides = so,
            attr_translate    = self.toolchain.attr_translate,
            **kwargs
        )

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

    def add_false_path_constraint(self, from_, to):
        if hasattr(from_, "p"):
            from_ = from_.p
        if hasattr(to, "p"):
            to = to.p
        from_.attr.add("keep")
        to.attr.add("keep")
        self.toolchain.add_false_path_constraint(self, from_, to)
