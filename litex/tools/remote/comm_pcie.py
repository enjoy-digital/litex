#
# This file is part of LiteX.
#
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import mmap
import ctypes
import subprocess

from litex.tools.remote.csr_builder import CSRBuilder

# CommPCIe -----------------------------------------------------------------------------------------

class CommPCIe(CSRBuilder):
    def __init__(self, bar, csr_csv=None, debug=False):
        # Initialize CSRBuilder and set up BAR path.
        CSRBuilder.__init__(self, comm=self, csr_csv=csr_csv)
        if "/sys/bus/pci/devices" not in bar:
            bar = f"/sys/bus/pci/devices/0000:{bar}/resource0"
        self.bar         = bar
        self.enable_path = self.bar.replace("resource0", "enable")
        self.debug       = debug
        # Ensure accessibility for enable and resource files.
        self._make_accessible(self.enable_path)
        self._make_accessible(self.bar)

        self.enable()

    def _make_accessible(self, path):
        # Change file permissions to allow access (with sudo if needed).
        cmd = ["chmod", "666", path]
        if os.geteuid() != 0:
            cmd = ["sudo"] + cmd
        subprocess.check_call(cmd, stderr=subprocess.DEVNULL)

    def enable(self):
        # Enable PCIe device if not already enabled.
        with open(self.enable_path, "r+") as enable:
            if enable.read(1) == "0":
                enable.seek(0)
                enable.write("1")

    def open(self):
        # Open the BAR file and create mmap.
        if hasattr(self, "file"):
            return
        self.file = os.open(self.bar, os.O_RDWR | os.O_SYNC)
        self.size = os.fstat(self.file).st_size
        self.mmap = mmap.mmap(self.file, self.size, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ | mmap.PROT_WRITE)

    def close(self):
        # Close the file and mmap.
        if not hasattr(self, "file"):
            return
        self.file.close()
        del self.file
        self.mmap.close()

    def read(self, addr, length=None, burst="incr"):
        # Read data from mmap (incr burst only).
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
        # Write data to mmap.
        data = data if isinstance(data, list) else [data]
        for i, value in enumerate(data):
            ctypes.c_uint32.from_buffer(self.mmap, addr + 4*i).value = value
            if self.debug:
                print("write 0x{:08x} @ 0x{:08x}".format(value, addr + 4*i))
