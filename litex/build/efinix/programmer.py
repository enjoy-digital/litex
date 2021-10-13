#
# This file is part of LiteX.
#
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import subprocess

from litex.build.generic_programmer import GenericProgrammer

# EfinixProgrammer ---------------------------------------------------------------------------------

class EfinixProgrammer(GenericProgrammer):

    def __init__(self, cable_name=""):
        self.cable_name = cable_name
        if os.getenv("LITEX_ENV_EFINITY", False) == False:
            msg = "Unable to find or source Efinity toolchain, please either:\n"
            msg += "- Set LITEX_ENV_EFINITY environment variant to Efinity path.\n"
            msg += "- Or add Efinity toolchain to your $PATH."
            raise OSError(msg)

        self.efinity_path = os.environ["LITEX_ENV_EFINITY"].rstrip('/')
        os.environ["EFINITY_HOME"] = self.efinity_path

    def load_bitstream(self, bitstream_file, cable_suffix=""):
        os.environ['EFXPGM_HOME'] = self.efinity_path + '/pgm'
        if (subprocess.call([self.efinity_path + '/bin/python3', self.efinity_path +
                   '/pgm/bin/efx_pgm/ftdi_program.py', bitstream_file,
                   "-m", "jtag"], env=os.environ.copy()) != 0):
            msg = f"Error occured during {self.__class__.__name__}'s call, please check:\n"
            msg += f"- {self.__class__.__name__} installation.\n"
            msg += f"- access permissions.\n"
            msg += f"- hardware and cable."
            raise OSError(msg)
