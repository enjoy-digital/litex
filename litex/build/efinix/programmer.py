#
# This file is part of LiteX.
#
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys

from litex.build.generic_programmer import GenericProgrammer

class EfinixProgrammer(GenericProgrammer):

    def __init__(self, cable_name=""):
        self.cable_name = cable_name
        if 'LITEX_ENV_EFINITY' in os.environ:
            self.efinity_path = os.environ['LITEX_ENV_EFINITY'].rstrip('/')
            os.environ['EFINITY_HOME'] = self.efinity_path
        else:
            raise OSError('Unable to find Efinity toolchain, please set LITEX_ENV_EFINITY to ${install_dir}')

    def load_bitstream(self, bitstream_file, cable_suffix=""):
        os.environ['EFXPGM_HOME'] = self.efinity_path + '/pgm'
        self.call([self.efinity_path + '/bin/python3', self.efinity_path +
                   'pgm/bin/efx_pgm/ftdi_program.py', bitstream_file,
                   "-m", "jtag"
        ])
