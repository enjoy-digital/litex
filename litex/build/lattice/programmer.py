#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2017-2018 William D. Jones <thor0505@comcast.net>
# SPDX-License-Identifier: BSD-2-Clause

import os

from litex.build.generic_programmer import GenericProgrammer
from litex.build import tools

# LatticeProgrammer --------------------------------------------------------------------------------

class LatticeProgrammer(GenericProgrammer):
    needs_bitreverse = False

    def __init__(self, xcf_template):
        self.xcf_template = xcf_template

    def load_bitstream(self, bitstream_file):
        xcf_file = bitstream_file.replace(".bit", ".xcf")
        xcf_content = self.xcf_template.format(bitstream_file=bitstream_file)
        tools.write_to_file(xcf_file, xcf_content)
        self.call(["pgrcmd", "-infile", xcf_file], check=False)

# OpenOCDJTAGProgrammer ----------------------------------------------------------------------------

class OpenOCDJTAGProgrammer(GenericProgrammer):
    def __init__(self, config, flash_proxy_basename=None):
        GenericProgrammer.__init__(self, flash_proxy_basename)
        self.config = config

    def load_bitstream(self, bitstream_file):
        config   = self.find_config()
        assert bitstream_file.endswith(".bit") or bitstream_file.endswith(".svf")
        if bitstream_file.endswith(".bit"):
            from litex.build.lattice.bit_to_svf import bit_to_svf
            bit = bitstream_file
            svf = bit.replace(".bit", ".svf")
            bit_to_svf(bit=bit, svf=svf)
        else:
            svf = bitstream_file
        self.call(["openocd", "-f", config, "-c", "transport select jtag; init; svf quiet progress \"{}\"; exit".format(svf)])

    def flash(self, address, data, verify=True):
        config      = self.find_config()
        flash_proxy = self.find_flash_proxy()
        script = "; ".join([
            "transport select jtag",
            "target create ecp5.spi0.proxy testee -chain-position ecp5.tap",
            "flash bank spi0 jtagspi 0 0 0 0 ecp5.spi0.proxy 0x32",
            "init",
            "svf quiet progress \"{}\"".format(flash_proxy),
            "reset halt",
            "flash probe spi0",
            "flash write_image erase \"{0}\" 0x{1:x}".format(data, address),
            "flash verify_bank spi0 \"{0}\" 0x{1:x}" if verify else "".format(data, address),
            "exit"
        ])
        self.call(["openocd", "-f", config, "-c", script])

# IceStormProgrammer -------------------------------------------------------------------------------

class IceStormProgrammer(GenericProgrammer):
    needs_bitreverse = False

    def flash(self, address, bitstream_file):
        self.call(["iceprog", "-o", str(address), bitstream_file])

    def load_bitstream(self, bitstream_file):
        self.call(["iceprog", "-S", bitstream_file])

# IceSugarProgrammer -------------------------------------------------------------------------------

class IceSugarProgrammer(GenericProgrammer):
    needs_bitreverse = False

    def flash(self, address, bitstream_file):
        self.call(["icesprog", "-o", str(address), bitstream_file])

    def load_bitstream(self, bitstream_file):
        self.call(["icesprog", bitstream_file])

# IceBurnProgrammer --------------------------------------------------------------------------------

class IceBurnProgrammer(GenericProgrammer):
    def __init__(self, iceburn_path):
        GenericProgrammer.__init__(self)
        self.iceburn = iceburn_path

    needs_bitreverse = False

    def load_bitstream(self, bitstream_file):
        self.call([self.iceburn, "-evw", bitstream_file])

# TinyFpgaBProgrammer ------------------------------------------------------------------------------

class TinyFpgaBProgrammer(GenericProgrammer):
    needs_bitreverse = False

    # The default flash address you probably want is 0x30000; the image at
    # address 0 is for the bootloader.
    def flash(self, address, bitstream_file):
        self.call(["tinyfpgab", "-a", str(address), "-p",
                        bitstream_file])

    # Force user image to boot if a user reset tinyfpga, the bootloader
    # is active, and the user image need not be reprogrammed.
    def boot(self):
        self.call(["tinyfpgab", "-b"])

# TinyProgProgrammer -------------------------------------------------------------------------------

# Different bootloader protocol requires different application. In the basic
# case, command-line arguments are the same. Note that this programmer can
# also be used with TinyFPGA B2 if you have updated its bootloader.
class TinyProgProgrammer(GenericProgrammer):
    needs_bitreverse = False

    # You probably want to pass address="None" for this programmer
    # unless you know what you're doing.
    def flash(self, address, bitstream_file, user_data=False):
        if address is None:
            if not user_data:
                # tinyprog looks at spi flash metadata to figure out where to
                # program your bitstream.
                self.call(["tinyprog", "-p", bitstream_file])
            else:
                # Ditto with user data.
                self.call(["tinyprog", "-u", bitstream_file])
        else:
            # Provide override so user can program wherever they wish.
            self.call(["tinyprog", "-a", str(address), "-p",
                            bitstream_file])

    # Force user image to boot if a user reset tinyfpga, the bootloader
    # is active, and the user image need not be reprogrammed.
    def boot(self):
        self.call(["tinyprog", "-b"])

# MyStormProgrammer --------------------------------------------------------------------------------

class MyStormProgrammer(GenericProgrammer):
    def __init__(self, serial_port):
        self.serial_port = serial_port

    def load_bitstream(self, bitstream_file):
        import serial
        with serial.Serial(self.serial_port) as port:
            with open(bitstream_file, "rb") as f:
                port.write(f.read())

# UJProg -------------------------------------------------------------------------------------------

class UJProg(GenericProgrammer):
    needs_bitreverse = False

    def load_bitstream(self, bitstream_file):
        self.call(["ujprog", bitstream_file])

# EcpDapProgrammer ---------------------------------------------------------------------------------

class EcpDapProgrammer(GenericProgrammer):
    """ECPDAP allows you to program ECP5 FPGAs and attached SPI flash using CMSIS-DAP probes in JTAG mode.

    You can get `ecpdap` here: https://github.com/adamgreig/ecpdap
    """
    needs_bitreverse = False

    def __init__(self, frequency=8_000_000):
        self.frequency = frequency

    def flash(self, address, bitstream_file):
        self.call(["ecpdap",
            "flash", "write",
            "--freq", str(self.frequency),
            "--offset", str(address),
            bitstream_file
        ])

    def load_bitstream(self, bitstream_file):
        self.call(["ecpdap",
            "program",
            "--freq", str(self.frequency),
            bitstream_file
        ])

# EcpprogProgrammer -------------------------------------------------------------------------------

class EcpprogProgrammer(GenericProgrammer):
    """ecpprog allows you to program ECP5 FPGAs and attached SPI flash using FTDI based JTAG probes

    You can get `ecpprog` here: https://github.com/gregdavill/ecpprog
    """
    needs_bitreverse = False

    def flash(self, address, bitstream_file):
        self.call(["ecpprog", "-o", str(address), bitstream_file])

    def load_bitstream(self, bitstream_file):
        self.call(["ecpprog", "-S", bitstream_file])
