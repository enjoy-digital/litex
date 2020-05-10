# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2017-2018 William D. Jones <thor0505@comcast.net>
# License: BSD

import os
import subprocess

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
        subprocess.call(["pgrcmd", "-infile", xcf_file])

# OpenOCDJTAGProgrammer --------------------------------------------------------------------------------

class OpenOCDJTAGProgrammer(GenericProgrammer):
    def __init__(self, config, flash_proxy_basename=None):
        GenericProgrammer.__init__(self, flash_proxy_basename)
        self.config = config

    def load_bitstream(self, bitstream_file):
        config   = self.find_config()
        svf_file = bitstream_file.replace(".bit", ".svf")
        subprocess.call(["openocd", "-f", config, "-c", "transport select jtag; init; svf quiet progress \"{}\"; exit".format(svf_file)])

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
        subprocess.call(["openocd", "-f", config, "-c", script])

# IceStormProgrammer -------------------------------------------------------------------------------

class IceStormProgrammer(GenericProgrammer):
    needs_bitreverse = False

    def flash(self, address, bitstream_file):
        subprocess.call(["iceprog", "-o", str(address), bitstream_file])

    def load_bitstream(self, bitstream_file):
        subprocess.call(["iceprog", "-S", bitstream_file])

# IceBurnProgrammer --------------------------------------------------------------------------------

class IceBurnProgrammer(GenericProgrammer):
    def __init__(self, iceburn_path):
        GenericProgrammer.__init__(self)
        self.iceburn = iceburn_path

    needs_bitreverse = False

    def load_bitstream(self, bitstream_file):
        subprocess.call([self.iceburn, "-evw", bitstream_file])

# TinyFpgaBProgrammer ------------------------------------------------------------------------------

class TinyFpgaBProgrammer(GenericProgrammer):
    needs_bitreverse = False

    # The default flash address you probably want is 0x30000; the image at
    # address 0 is for the bootloader.
    def flash(self, address, bitstream_file):
        subprocess.call(["tinyfpgab", "-a", str(address), "-p",
                        bitstream_file])

    # Force user image to boot if a user reset tinyfpga, the bootloader
    # is active, and the user image need not be reprogrammed.
    def boot(self):
        subprocess.call(["tinyfpgab", "-b"])

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
                subprocess.call(["tinyprog", "-p", bitstream_file])
            else:
                # Ditto with user data.
                subprocess.call(["tinyprog", "-u", bitstream_file])
        else:
            # Provide override so user can program wherever they wish.
            subprocess.call(["tinyprog", "-a", str(address), "-p",
                            bitstream_file])

    # Force user image to boot if a user reset tinyfpga, the bootloader
    # is active, and the user image need not be reprogrammed.
    def boot(self):
        subprocess.call(["tinyprog", "-b"])

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
        subprocess.call(["ujprog", bitstream_file])
