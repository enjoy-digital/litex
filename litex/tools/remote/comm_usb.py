#
# This file is part of LiteX.
#
# Copyright (c) 2019 Sean Cross <sean@xobs.io>
# SPDX-License-Identifier: BSD-2-Clause

import usb.core
import time

from litex.tools.remote.csr_builder import CSRBuilder

# Wishbone USB Protocol Bridge
# ============================
#
# This module implements a bridge to connect LiteX to the target system's
# Wishbone bus via USB.  It uses `vendor` packets to communicate, which are
# normally reserved.  Since we're the vendors of this USB protocol, we take
# advantage of this packet type to implement the bridge.
#
# All traffic goes to/from USB EP0, which is guaranteed to exist regardless
# of the user's device implementation.  The 8th bit of the first SETUP DATA
# transaction contains all the information we need to mark this as a
# Wishbone packet.
#
# Packets going to EP0 always start with a SETUP packet, followed by an IN
# or an OUT packet, followed by an OUT or an IN packet.
#
# The SETUP packet looks like this:
#
# +----+----+----------+----+----+
# | C3 | 00 | ADDRESS  | 04 | 00 |   read packet
# +----+----+----------+----+----+
#   1    1        4      1    1
#
# +----+----+----------+----+----+
# | 43 | 00 | ADDRESS  | 04 | 00 |   write packet
# +----+----+----------+----+----+
#   1    1        4      1    1
#
# If the transaction is a "read" transaction, the device responds with an OUT
# packet with the data.  If the transaction is a "write" transaction, the host
# responds with an IN packet with the data.
#
# Much like other Wishbone bridges, there are two types of packets.  The first
# byte indicates what type of packet it is, and that it is a Wishbone Bridge
# packet.  This is the value "0x40" (VENDOR type packet destined for DEVICE)
# with the "Data Phase Transfer" bit either set or cleared:
#     - Read:  0xc3
#     - Write: 0x43
#
# The next byte is bRequest, which in the current implementation is unused.
# Set this value to 0.
#
# The next four bytes form the wValue and wIndex values of the SETUP token.
# We reuse these two 16-bit values as a single 32-bit ADDRESS packet.  Note that
# USB is big endian.
#
# Finally, the last two bytes indicate the length of the transaction.  Since
# we only support 32-bit reads and writes, this is always 4.  On big endian
# USB, this has the value {04, 00}.

# CommUSB ------------------------------------------------------------------------------------------

class CommUSB(CSRBuilder):
    def __init__(self, vid=None, pid=None, max_retries=10, csr_csv=None, debug=False):
        CSRBuilder.__init__(self, comm=self, csr_csv=csr_csv)
        self.vid         = vid
        self.pid         = pid
        self.debug       = debug
        self.max_retries = max_retries
        self.max_recursion_count = 5

    def open(self):
        if hasattr(self, "dev"):
            return
        for t in range(self.max_retries):
            args = {}
            if self.vid is not None:
                args['idVendor'] = self.vid
            if self.pid is not None:
                args['idProduct'] = self.pid
            self.dev = usb.core.find(**args)
            if self.dev is not None:
                if self.debug:
                    print("device connected after {} tries".format(t+1))
                return True
            del self.dev
            time.sleep(0.2 * t)
        print("unable to find usb device after {} tries".format(self.max_retries))
        return False


    def close(self):
        if not hasattr(self, "dev"):
            return
        del self.dev

    def read(self, addr, length=None, burst="incr"):
        assert burst == "incr"
        data = []
        length_int = 1 if length is None else length
        for i in range(length_int):
            value = self.usb_read(addr)
            # Note that sometimes, the value ends up as None when the device
            # disconnects during a transaction.  Paper over this fact by
            # replacing it with a sentinal.
            if value is None:
                value = 0xffffffff
            if self.debug:
                print("read 0x{:08x} @ 0x{:08x}".format(value, addr))
            if length is None:
                return value
            data.append(value)
        return data

    def usb_read(self, addr, depth=0):
        try:
            value = self.dev.ctrl_transfer(bmRequestType=0xc3,
                        bRequest=0x00,
                        wValue=addr & 0xffff,
                        wIndex=(addr >> 16) & 0xffff,
                        data_or_wLength=4)
            if value is None:
                raise TypeError
            return int.from_bytes(value, byteorder="little")
        except usb.core.USBError as e:
            if e.errno == 13:
                print("Access Denied. Maybe try using sudo?")
            self.close()
            self.open()
            if depth < self.max_recursion_count:
                return self.usb_read(addr, depth+1)
        except TypeError:
            self.close()
            self.open()
            if depth < self.max_recursion_count:
                return self.usb_read(addr, depth+1)

    def write(self, addr, data):
        data = data if isinstance(data, list) else [data]
        length = len(data)
        for i, value in enumerate(data):
            self.usb_write(addr, value)
            if self.debug:
                print("write 0x{:08x} @ 0x{:08x}".format(value, addr + 4*i))

    def usb_write(self, addr, value, depth=0):
        try:
            value = self.dev.ctrl_transfer(bmRequestType=0x43, bRequest=0x00,
                    wValue=addr & 0xffff,
                    wIndex=(addr >> 16) & 0xffff,
                    data_or_wLength=bytes([(value >> 0) & 0xff,
                                           (value >> 8) & 0xff,
                                           (value >> 16) & 0xff,
                                           (value >> 24) & 0xff]
                                          ), timeout=None)
        except usb.core.USBError as e:
            if e.errno == 13:
                print("Access Denied. Maybe try using sudo?")
            self.close()
            self.open()
            if depth < self.max_recursion_count:
                return self.usb_write(addr, value, depth+1)
