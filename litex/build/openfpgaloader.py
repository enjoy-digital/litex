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

    def __init__(self, board="", cable="", freq=0, fpga_part="", index_chain=None, ftdi_serial=None):
        # openFPGALoader base command.
        self.cmd = ["openFPGALoader"]

        # Specify FPGA board.
        if board:
            self.cmd += ["--board", board]

        # Specify FPGA part/device.
        if fpga_part:
            self.cmd += ["--fpga-part", fpga_part]

        # Specify programmation cable.
        if cable:
            self.cmd += ["--cable", cable]

        # Specify programmation frequency.
        if freq:
            self.cmd += ["--freq", str(int(float(freq)))]

        # Specify index in the JTAG chain.
        if index_chain is not None:
            self.cmd += ["--index-chain", str(int(index_chain))]

        if ftdi_serial is not None:
            self.cmd += ["--ftdi-serial", str(ftdi_serial)]

    def load_bitstream(self, bitstream_file):
        # Load base command.
        cmd = self.cmd + ["--bitstream", bitstream_file]

        # Execute command.
        print(" ".join(cmd))
        self.call(cmd)

    def flash(self, address, data_file, external=False, unprotect_flash=False, verify=False, **kwargs):
        # Flash base command.
        cmd = self.cmd + ["--write-flash", "--bitstream", data_file]

        # Flash Internal/External selection.
        if external:
            cmd += ["--external-flash"]

        # Flash Offset.
        if address:
            cmd += ["--offset"]
            cmd += [str(address)]

        # Flash Unprotect.
        if unprotect_flash:
            cmd += ["--unprotect-flash"]

        # Flash Verify.
        if verify:
            cmd += ["--verify"]

        # Handle kwargs for specific, less common cases.
        for key, value in kwargs.items():
            cmd.append(f"--{key.replace('_', '-')}")
            if value is not None:
                cmd.append(str(value))

        # Execute Command.
        try:
            print(" ".join(cmd))
            self.call(cmd)
        except OSError as e:
            print(' '.join(cmd))
            raise

    def reset(self):
        # Reset base command.
        cmd = self.cmd + ["--reset"]

        # Execute command.
        print(" ".join(cmd))
        self.call(cmd)
