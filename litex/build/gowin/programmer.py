#
# This file is part of LiteX.
#
# Copyright (c) 2022 Franz Zhou <curliph@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
from shutil import which

from litex.build.generic_programmer import GenericProgrammer
from litex.build import tools

# GowinProgrammer ----------------------------------------------------------------------------------

GOWIN_PMODE_SRAM = 4
GOWIN_PMODE_EMBFLASH = 5
GOWIN_PMODE_EXTFLASH = 31 # for bin 

GOWIN_CABLE_GWU2X = 0
GOWIN_CABLE_FT2CH = 1

# for all other options, please run 'programmer_cli -h' for details
# feel free to add any options for your purpose.

class GowinProgrammer(GenericProgrammer):
    needs_bitreverse = False

    def __init__(self, devname):
        self.device = str(devname)

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
    #  2. External SPI FLASH programming is also not detailed (for programmer_cli) 
    #  3. Verify usually got stuck, so we disable it by now. patch is welcome!
    def flash(self, address = 0, data_file = None, external = False, fifile = None, verify = False, cable = GOWIN_CABLE_FT2CH):
        pmode = (GOWIN_PMODE_EMBFLASH + 1) if verify else GOWIN_PMODE_EMBFLASH

        if external is True:
            pmode = (GOWIN_PMODE_EXTFLASH + 1) if verify else GOWIN_PMODE_EXTFLASH

        if data_file is None and fifile is None:
            print("GowinProgrammer: fsFile or fiFile should be given!");
            exit(1)

        if self.is_wsl is True and data_file is not None:
            data_file = os.popen("wslpath -w {}".format(data_file)).read().strip("\n") 

        if self.is_wsl is True and fifile is not None:
            fifile = os.popen("wslpath -w {}".format(fifile)).read().strip("\n")

        cmd_line = [self.programmer, 
                "--spiaddr", str(address),
                "--device", str(self.device)]

        if data_file is not None:
            if external is True:
                cmd_line += ["--mcuFile", str(data_file)]
            else:
                cmd_line += ["--fsFile", str(data_file)]

        if fifile is not None:
            cmd_line += ["--fiFile", str(fifile)]

        cmd_line += ["--cable-index", str(cable), "--operation_index", str(pmode)]
        self.call(cmd_line)

    def load_bitstream(self, bitstream_file, verify = False, cable = GOWIN_CABLE_FT2CH):
        pmode = 4 if verify else 2
        bitfile = bitstream_file
        if self.is_wsl is True:
            bitfile = os.popen("wslpath -w {}".format(bitstream_file)).read().strip("\n")
            
        cmd_line = [self.programmer,
            "--device", str(self.device),
            "--fsFile", str(bitfile),
            "--cable-index", str(cable),
            "--operation_index", str(pmode)]
        self.call(cmd_line)
