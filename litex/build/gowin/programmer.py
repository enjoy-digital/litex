#
# This file is part of LiteX.
#
# Copyright (c) 2022 Franz Zhou <curliph@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
from shutil import which

from litex.build.generic_programmer import GenericProgrammer

# GowinProgrammer ----------------------------------------------------------------------------------

# SRAM Program
GOWIN_PMODE_SRAM = 2
# SRAM Program JTAG 1149
GOWIN_PMODE_SRAM_JTAG = 16
# embFlash Erase,Program
GOWIN_PMODE_EMBFLASH = 5
# exFlash C Bin Erase,Program thru GAO-Bridge
GOWIN_PMODE_EXFLASH_BIN = 38
# exFlash Erase,Program thru GAO-Bridge
GOWIN_PMODE_EXFLASH = 36

GOWIN_CABLE_GWU2X = 0
GOWIN_CABLE_FT2CH = 1

# for all other options, please run 'programmer_cli -h' for details
# feel free to add any options for your purpose.

class GowinProgrammer(GenericProgrammer):
    needs_bitreverse = False

    def __init__(self, devname, cable = GOWIN_CABLE_FT2CH):
        self.device = str(devname)
        self.cable = cable

        # Ref: Gowin Programmer User Guide https://cdn.gowinsemi.com.cn/SUG502E.pdf
        self.has_embflash = self.device.startswith("GN1N")

        # windows/powershell or msys2
        self.is_win32 = True if sys.platform == "win32" else False

        self.is_wsl = False
        if sys.platform.find("linux") >= 0:
            self.is_wsl = os.uname().release.find("WSL") > 0

        self.programmer = "programmer_cli"

        # note for WSL:
        # gowin programmer_cli not working out of it's directory
        if self.is_wsl or self.is_win32:
            self.programmer += ".exe"

            gw_dir = which(self.programmer)
            if gw_dir is not None:
                gw_dir = os.path.dirname(gw_dir)
                os.chdir(gw_dir)

    # follow the help information:
    #  1. Gowin programmer does not support start address for embflash!
    #  2. Verify usually got stuck, so we disable it by now. patch is welcome!
    def flash(self, address = 0, bitstream_file = None, external = False, fifile = None, mcufile = None, pmode = None):

        if pmode is None:
            if external:
                pmode = GOWIN_PMODE_EXFLASH
            elif self.has_embflash:
                pmode = GOWIN_PMODE_EMBFLASH
            else:
                pmode = GOWIN_PMODE_EXFLASH
                external = True

        if bitstream_file is None and fifile is None and mcufile is None:
            print("GowinProgrammer: fsFile, fiFile or mcuFile should be given!")
            exit(1)

        if self.is_wsl is True and bitstream_file is not None:
            bitstream_file = os.popen("wslpath -w {}".format(bitstream_file)).read().strip("\n")

        if self.is_wsl is True and fifile is not None:
            fifile = os.popen("wslpath -w {}".format(fifile)).read().strip("\n")

        if self.is_wsl is True and mcufile is not None:
            mcufile = os.popen("wslpath -w {}".format(mcufile)).read().strip("\n")

        cmd_line = [
            self.programmer,
            "--device", str(self.device)]

        if external:
            # accepts 0xXXX, at least 3 hex digits. Here we use 6 digits.
            spiaddr = "0x{:05X}".format(address)
            cmd_line += ["--spiaddr", spiaddr]

        if bitstream_file is not None:
            cmd_line += ["--fsFile", str(bitstream_file)]

        if fifile is not None:
            cmd_line += ["--fiFile", str(fifile)]

        if mcufile is not None:
            cmd_line += ["--mcuFile", str(mcufile)]

        cmd_line += ["--cable-index", str(self.cable), "--operation_index", str(pmode)]
        print(' '.join(cmd_line))
        self.call(cmd_line)

    def load_bitstream(self, bitstream_file):
        pmode = GOWIN_PMODE_SRAM
        bitfile = bitstream_file
        if self.is_wsl is True:
            bitfile = os.popen("wslpath -w {}".format(bitstream_file)).read().strip("\n")

        cmd_line = [self.programmer,
            "--device", str(self.device),
            "--fsFile", str(bitfile),
            "--cable-index", str(self.cable),
            "--operation_index", str(pmode)]
        self.call(cmd_line)
