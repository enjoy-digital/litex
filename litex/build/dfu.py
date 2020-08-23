#
# This file is part of LiteX.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import subprocess

from litex.build.tools import write_to_file
from litex.build.generic_programmer import GenericProgrammer

# DFUProg ------------------------------------------------------------------------------------------

class DFUProg(GenericProgrammer):
    needs_bitreverse = False

    def __init__(self, vid, pid):
        self.vid = vid
        self.pid = pid

    def load_bitstream(self, bitstream_file):
        subprocess.call(["cp", bitstream_file, bitstream_file + ".dfu"])
        subprocess.call(["dfu-suffix", "-v", self.vid, "-p", self.pid, "-a", bitstream_file + ".dfu"])
        subprocess.call(["dfu-util", "--download", bitstream_file + ".dfu"])
