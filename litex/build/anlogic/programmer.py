#
# This file is part of LiteX.
#
# Copyright (c) 2015-2025 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2025 Junhui Liu <junhui.liu@pigmoral.tech>
# SPDX-License-Identifier: BSD-2-Clause

import subprocess
from shutil import which

from litex.build.generic_programmer import GenericProgrammer

def _run_td(cmds):
    if which("td") is None:
        msg = "Unable to find Tang Dinasty toolchain, please:\n"
        msg += "- Add Tang Dinasty toolchain to your $PATH."
        raise OSError(msg)

    with subprocess.Popen("td", stdin=subprocess.PIPE, shell=True) as process:
        process.stdin.write(cmds.encode("ASCII"))
        process.communicate()

class TangDynastyProgrammer(GenericProgrammer):
    def __init__(self):
        GenericProgrammer.__init__(self)

    def load_bitstream(self, bitstream_file):
        cmds = """download -bit {bitstream} -mode jtag -spd 7 -sec 64 -cable 0
exit
""".format(bitstream=bitstream_file)
        _run_td(cmds)
