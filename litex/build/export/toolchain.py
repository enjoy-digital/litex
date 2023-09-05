#
# This file is part of LiteX.
#
# Copyright (c) 2023 Josuah Demangeon <me@josuah.net>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.generic_toolchain import GenericToolchain

# ExportToolchain ----------------------------------------------------------------------------------

class ExportToolchain(GenericToolchain):
    special_overrides = {}

    def build_io_constraints(self):
        pass

    def build_script(self):
        pass

    def run_script(self, script):
        pass
