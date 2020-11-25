#
# This file is part of LiteX.
#
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import serial
import struct

from litex.tools.remote.csr_builder import CSRBuilder

# Constants ----------------------------------------------------------------------------------------

CMD_WRITE_BURST_INCR  = 0x01
CMD_READ_BURST_INCR   = 0x02
CMD_WRITE_BURST_FIXED = 0x03
CMD_READ_BURST_FIXED  = 0x04

# CommUART -----------------------------------------------------------------------------------------

class CommUART(CSRBuilder):
    def __init__(self, port, baudrate=115200, csr_csv=None, debug=False):
        CSRBuilder.__init__(self, comm=self, csr_csv=csr_csv)
        self.port     = serial.serial_for_url(port, baudrate)
        self.baudrate = str(baudrate)
        self.debug    = debug

    def open(self):
        if hasattr(self, "port"):
            return
        self.port.open()

    def close(self):
        if not hasattr(self, "port"):
            return
        self.port.close()
        del self.port

    def _read(self, length):
        r = bytes()
        while len(r) < length:
            r += self.port.read(length - len(r))
        return r

    def _write(self, data):
        remaining = len(data)
        pos = 0
        while remaining:
            written = self.port.write(data[pos:])
            remaining -= written
            pos += written

    def _flush(self):
        if self.port.inWaiting() > 0:
            self.port.read(self.port.inWaiting())

    def read(self, addr, length=None, burst="incr"):
        self._flush()
        data       = []
        length_int = 1 if length is None else length
        cmd        = {
            "incr" : CMD_READ_BURST_INCR,
            "fixed": CMD_READ_BURST_FIXED,
        }[burst]
        self._write([cmd, length_int])
        self._write(list((addr//4).to_bytes(4, byteorder="big")))
        for i in range(length_int):
            value = int.from_bytes(self._read(4), "big")
            if self.debug:
                print("read 0x{:08x} @ 0x{:08x}".format(value, addr + 4*i))
            if length is None:
                return value
            data.append(value)
        return data

    def write(self, addr, data, burst="incr"):
        self._flush()
        data   = data if isinstance(data, list) else [data]
        length = len(data)
        offset = 0
        while length:
            size = min(length, 8)
            cmd = {
                "incr" : CMD_WRITE_BURST_INCR,
                "fixed": CMD_WRITE_BURST_FIXED,
            }[burst]
            self._write([cmd, size])
            self._write(list(((addr//4 + offset).to_bytes(4, byteorder="big"))))
            for i, value in enumerate(data[offset:offset+size]):
                self._write(list(value.to_bytes(4, byteorder="big")))
                if self.debug:
                    print("write 0x{:08x} @ 0x{:08x}".format(value, addr + offset, 4*i))
            offset += size
            length -= size
