#
# This file is part of LiteX.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import subprocess

from litex.build.tools import write_to_file
from litex.build.generic_programmer import GenericProgrammer

# openFPGAloader ------------------------------------------------------------------------------------------

class OpenFPGALoader(GenericProgrammer):
    needs_bitreverse = False

    def __init__(self, board):
        self.board = board

    def load_bitstream(self, bitstream_file):
        subprocess.call(["openFPGALoader", "--board", self.board, bitstream_file])
