#
# This file is part of LiteX.
#
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import ctypes
import mmap

from litex.tools.remote.csr_builder import CSRBuilder

# CommPCIe -----------------------------------------------------------------------------------------

class CommPCIe(CSRBuilder):
    def __init__(self, bar, csr_csv=None, debug=False):
        CSRBuilder.__init__(self, comm=self, csr_csv=csr_csv)
        if "/sys/bus/pci/devices" not in bar:
            bar = f"/sys/bus/pci/devices/0000:{bar}/resource0"
        self.bar   = bar
        self.debug = debug

        self.enable()

    def enable(self):
        # Enable PCIe device is not already enabled.
        enable = open(self.bar.replace("resource0", "enable"), "r+")
        if enable.read(1) == "0":
            enable.seek(0)
            enable.write("1")
        enable.close()

    def open(self):
        if hasattr(self, "file"):
            return
        self.file = os.open(self.bar, os.O_RDWR | os.O_SYNC)
        self.mmap = mmap.mmap(self.file, 0)

    def close(self):
        if not hasattr(self, "file"):
            return
        self.file.close()
        del self.file
        self.mmap.close()

    def read(self, addr, length=None, burst="incr"):
        assert burst == "incr"
        data = []
        length_int = 1 if length is None else length
        for i in range(length_int):
            value = ctypes.c_uint32.from_buffer(self.mmap, addr + 4*i).value
            if self.debug:
                print("read 0x{:08x} @ 0x{:08x}".format(value, addr + 4*i))
            if length is None:
                return value
            data.append(value)
        return data

    def write(self, addr, data):
        data = data if isinstance(data, list) else [data]
        length = len(data)
        for i, value in enumerate(data):
            ctypes.c_uint32.from_buffer(self.mmap, addr + 4*i).value = value
            if self.debug:
                print("write 0x{:08x} @ 0x{:08x}".format(value, addr + 4*i))
