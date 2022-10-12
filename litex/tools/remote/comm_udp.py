#
# This file is part of LiteX.
#
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2016 Tim 'mithro' Ansell <mithro@mithis.com>
# SPDX-License-Identifier: BSD-2-Clause

import socket
import time

from litex.tools.remote.etherbone import EtherbonePacket, EtherboneRecord
from litex.tools.remote.etherbone import EtherboneReads, EtherboneWrites

from litex.tools.remote.csr_builder import CSRBuilder

# CommUDP ------------------------------------------------------------------------------------------

class CommUDP(CSRBuilder):
    def __init__(self, server="192.168.1.50", port=1234, csr_csv=None, debug=False, timeout=1.0):
        CSRBuilder.__init__(self, comm=self, csr_csv=csr_csv)
        self.server = server
        self.port   = port
        self.debug  = debug
        self.timeout= timeout

    def open(self, probe=True):
        if hasattr(self, "socket"):
            return
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("", self.port))
        self.socket.settimeout(2)
        if probe:
            self.probe(self.server, self.port)

    def close(self):
        if not hasattr(self, "socket"):
            return
        self.socket.close()
        del self.socket

    def probe(self, ip, port, loose=False):

        packet = EtherbonePacket()
        packet.pf = 1
        packet.encode()
        packet.bytes += bytes([0x00, 0x00, 0x00, 0x00]) # Add Padding as payload.

        retries = 10
        self.socket.settimeout(self.timeout / retries)

        # Send probe request to server and get server's response.
        for r in range(retries):
            try:
                self.socket.sendto(packet.bytes, (ip, port))
                datas, dummy = self.socket.recvfrom(8192)
            except socket.timeout:
                if self.debug:
                    print("socket timeout, retrying ({}/{})".format(r+1, retries))
                continue
            break
        else:
            datas = None

        # Check the response
        if not loose and datas is None:
            raise Exception(f"Unable to probe Etherbone server at {self.server}.")

        if datas is not None:
            packet = EtherbonePacket(datas)
            packet.decode()
            assert packet.pr == 1
            return 1

        return 0

    def scan(self, ip="192.168.1.x"):
        print(f"Etherbone scan on {ip} network:")
        ip = ip.replace("x", "{}")
        self.socket.settimeout(0.01)
        for i in range(1, 255):
            if self.probe(ip=ip.format(str(i)), port=self.port, loose=True):
                print("- {}".format(ip.format(i)))
        self.socket.settimeout(1)

    def read(self, addr, length=None, burst="incr"):
        assert burst == "incr"
        length_int = 1 if length is None else length
        record = EtherboneRecord()
        record.reads = EtherboneReads(addrs=[addr+4*j for j in range(length_int)])
        record.rcount = len(record.reads)

        packet = EtherbonePacket()
        packet.records = [record]
        packet.encode()

        retries = 10

        self.socket.settimeout(self.timeout / retries)
        for r in range(retries):
            self.socket.sendto(packet.bytes, (self.server, self.port))
            try:
                datas, dummy = self.socket.recvfrom(8192)
            except socket.timeout:
                if self.debug:
                    print("socket timeout, retrying ({}/{})".format(r+1, retries))
                continue
            break
        else:
            raise socket.timeout

        packet = EtherbonePacket(datas)
        packet.decode()
        datas = packet.records.pop().writes.get_datas()
        if self.debug:
            for i, value in enumerate(datas):
                print("read 0x{:08x} @ 0x{:08x}".format(value, addr + 4*i))
        return datas[0] if length is None else datas

    def write(self, addr, datas):
        datas = datas if isinstance(datas, list) else [datas]
        length = len(datas)
        record = EtherboneRecord()
        record.writes = EtherboneWrites(base_addr=addr, datas=iter(datas))
        record.wcount = len(record.writes)

        packet = EtherbonePacket()
        packet.records = [record]
        packet.encode()

        self.socket.sendto(packet.bytes, (self.server, self.port))

        if self.debug:
            for i, value in enumerate(datas):
                print("write 0x{:08x} @ 0x{:08x}".format(value, addr + 4*i))
