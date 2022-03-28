#
# This file is part of LiteX.
#
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# Copyright (c) 2022 Charles-Henri Mousset <ch.mousset@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import time
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


class EfinixAtmelProgrammer:
    """Reimplementation of Efinix's 'atmel_program.py' used on the Triton T8F81 dev board."""
    """The original programmer only supports a single hexlified bitstream format, this one also"""
    """supports binaries programming"""

    vid = 0x03EB
    pid = 0x2013
    flash_erase_time = 7  # set to 20 in 'atmel_program.py' but W25Q80DV erases in 6s
    padding = 0xFF

    def __init__(self):
        import usb.core
        dev = usb.core.find(find_all=False, idVendor=self.vid, idProduct=self.pid)
        if not dev:
            raise ValueError(f"did not find Atmel USB programmer device with VID{self.vid:04x} PID{self.pid:04x}")
        dev.reset()
        reattach = False
        if os.name != 'nt':
            if dev.is_kernel_driver_active(0):
                reattach = True
                dev.detach_kernel_driver(0)
        dev.set_configuration()
        self.out_ep = dev[0][(0,0)][1]

        # Data payload
        self.payload = []

    def _expand_to_offset(self, offset):
        length = len(self.payload)
        if length < offset:
            self.payload += [self.padding] * (offset - length)
        elif length != 0:
            print(f"WARNING: potential overwrite of payload len={length} offset={offset}")

    def _usb_w(self, data):
        assert len(data) <= 64
        self.out_ep.write(data)

    def _prep_flash(self):
        self._usb_w([0x08])  # 'SPI Master'
        time.sleep(0.05)
        self._usb_w([0x09])  # 'flash_ready'
        time.sleep(0.05)

    def _prep_load(self):
        self._usb_w([0x0B])
        time.sleep(0.001)
        self._usb_w([0x0C])
        time.sleep(0.002)
        self._usb_w([0x0D])
        time.sleep(0.01)
        self._usb_w([0x01] + [self.padding] * 10)  # "write some initial junk bytes"

    def _finish_load(self):
        self._usb_w([0x0E])

    def _erase_flash(self):
        print("Erasing Flash...")
        self._usb_w([0x04])
        time.sleep(self.flash_erase_time)
        print("done")

    def _reload(self):
        self._usb_w([0x06] + [self.padding] * 63)  # toggle CRESET
        time.sleep(0.01)

    def _send_packet(self, packet, flash=False):
        """send 63 bytes of data"""
        assert len(packet) <= 63
        self._usb_w([0x03 if flash else 0x01] + packet)

    def _send_payload(self, flash=False):
        print(f"Sending {len(self.payload)} bytes data")
        CHUNK = 63
        payload = self.payload
        while payload:
            # print(f"payload l={len(payload)}")
            length = min(CHUNK, len(payload))
            packet = [self.padding] * CHUNK
            packet = payload[0:length]
            packet[0:length] = payload[0:length]
            payload = payload[length:]
            self._send_packet(packet, flash)

        self._usb_w([0x21] + [0xFF] * 63)  # 'close connection'
        time.sleep(0.01)
        print("done")

    def add_hex(self, offset, hexfile):
        """Efinix has a simple 'one line per byte, HEX-encoded' bitstream file"""
        with open(hexfile, 'r') as f:
            hexfile = f.read()
        lines = hexfile.split('\n')
        while lines[-1] == '':
            lines = lines[:-1]
        payload = [int(l[0:2], 16) for l in lines]
        length = len(payload)
        self._expand_to_offset(offset)
        self.payload[offset:+length] = payload

    def add_bin(self, offset, binfile):
        with open(binfile, 'rb') as f:
            payload = f.read()
        self._expand_to_offset(offset)
        self.payload[offset:+len(payload)] = payload

    def load(self):
        self._prep_load()
        self._send_payload()
        self._finish_load()

    def flash(self):
        self._prep_flash()
        self._erase_flash()
        self._prep_flash()
        self._send_payload(flash=True)
        self._reload()
