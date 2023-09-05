#
# This file is part of LiteX.
#
# Copyright (c) 2023 Josuah Demangeon <me@josuah.net>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.generic_platform import GenericPlatform
from litex.build.export.toolchain import ExportToolchain

# ExportPlatform -----------------------------------------------------------------------------------

class ExportPlatform(GenericPlatform):
    _supported_toolchains=["export"]

    def __init__(self, *args, **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)
        self.toolchain = ExportToolchain()

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        return GenericPlatform.get_verilog(self, *args,
            special_overrides = self.toolchain.special_overrides | special_overrides,
            attr_translate    = self.toolchain.attr_translate,
            **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

    def build_io_constraints(self):
        pass

    def add_false_path_constraint(self, from_, to):
        if hasattr(from_, "p"):
            from_ = from_.p
        if hasattr(to, "p"):
            to = to.p
        self.toolchain.add_false_path_constraint(self, from_, to)

    @classmethod
    def get_argdict(cls, toolchain, args):
        return {}
