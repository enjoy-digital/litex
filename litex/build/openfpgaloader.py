#
# This file is part of LiteX.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.tools import write_to_file
from litex.build.generic_programmer import GenericProgrammer

# OpenFPGALoader -----------------------------------------------------------------------------------

class OpenFPGALoader(GenericProgrammer):
    needs_bitreverse = False

    def __init__(self, board="", cable="", freq=0):
        self.cmd = ["openFPGALoader"]
        if board:
            self.cmd += ["--board", board]
        if cable:
            self.cmd += ["--cable", cable]
        if freq:
            self.cmd += ["--freq", str(int(float(freq)))]

    def load_bitstream(self, bitstream_file):
        cmd = self.cmd + ["--bitstream", bitstream_file]
        self.call(cmd)

    def flash(self, address, data_file, external=False):
        cmd = self.cmd + ["--write-flash", "--bitstream", data_file]
        if external:
            cmd += ["--external-flash"]
        if address:
            cmd += ["--offset"]
            cmd += [str(address)]
        self.call(cmd)
