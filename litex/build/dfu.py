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

    def __init__(self, vid, pid, alt=None):
        self.vid = vid
        self.pid = pid
        self.alt = alt

    def load_bitstream(self, bitstream_file, reset=True):
        subprocess.call(["cp", bitstream_file, bitstream_file + ".dfu"])
        subprocess.call(["dfu-suffix", "-v", self.vid, "-p", self.pid, "-a", bitstream_file + ".dfu"])

        flash_cmd = ["dfu-util", "--download", bitstream_file + ".dfu"]
        if reset:
            flash_cmd.append("-R")
        if self.alt is not None:
            flash_cmd.extend(["-a", str(self.alt)])
        subprocess.call(flash_cmd)
