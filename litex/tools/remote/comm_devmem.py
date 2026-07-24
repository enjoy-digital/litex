#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import mmap
import ctypes

from litex.tools.remote.csr_builder import CSRBuilder

# CommDevMem ---------------------------------------------------------------------------------------

class CommDevMem(CSRBuilder):
    """Direct /dev/mem access to a memory-mapped LiteX SoC.

    Useful when the LiteX SoC is accessible from a Hard CPU running Linux (ex Zynq7000's GP0 at
    0x4000_0000 or Cyclone V HPS's H2F LW bridge at 0xff20_0000): running litex_server --devmem on
    the Hard CPU then allows remote litex_cli/litescope accesses. Addresses are physical addresses;
    base/size define the mmap'ed window.
    """
    def __init__(self, base=0xff20_0000, size=0x0020_0000, dev="/dev/mem", csr_csv=None, debug=False):
        CSRBuilder.__init__(self, comm=self, csr_csv=csr_csv)
        self.base  = base
        self.size  = size
        self.dev   = dev
        self.debug = debug

    def open(self):
        # Open the device and create mmap.
        if hasattr(self, "file"):
            return
        self.file = os.open(self.dev, os.O_RDWR | os.O_SYNC)
        self.mmap = mmap.mmap(self.file, self.size,
            flags  = mmap.MAP_SHARED,
            prot   = mmap.PROT_READ | mmap.PROT_WRITE,
            offset = self.base,
        )

    def close(self):
        # Close the file and mmap.
        if not hasattr(self, "file"):
            return
        if hasattr(self, "mmap"):
            self.mmap.close()
            del self.mmap
        os.close(self.file)
        del self.file

    def _offset(self, addr):
        # Translate physical address to mmap offset (and check window).
        offset = addr - self.base
        assert 0 <= offset <= (self.size - 4), f"Address 0x{addr:08x} outside of DevMem window."
        return offset

    def read(self, addr, length=None, burst="incr"):
        # Read data from mmap (incr burst only).
        assert burst == "incr"
        data = []
        length_int = 1 if length is None else length
        for i in range(length_int):
            value = ctypes.c_uint32.from_buffer(self.mmap, self._offset(addr + 4*i)).value
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
            ctypes.c_uint32.from_buffer(self.mmap, self._offset(addr + 4*i)).value = value
            if self.debug:
                print("write 0x{:08x} @ 0x{:08x}".format(value, addr + 4*i))
