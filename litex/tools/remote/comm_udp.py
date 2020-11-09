#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2016 Tim 'mithro' Ansell <mithro@mithis.com>
# SPDX-License-Identifier: BSD-2-Clause

import socket

from litex.tools.remote.etherbone import EtherbonePacket, EtherboneRecord
from litex.tools.remote.etherbone import EtherboneReads, EtherboneWrites


class CommUDP:
    def __init__(self, server="192.168.1.50", port=1234, debug=False):
        self.server = server
        self.port = port
        self.debug = debug

    def open(self):
        if hasattr(self, "socket"):
            return
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("", self.port))

    def close(self):
        if not hasattr(self, "socket"):
            return
        self.socket.close()
        del self.socket

    def read(self, addr, length=None, burst="incr"):
        assert burst == "incr"
        length_int = 1 if length is None else length
        record = EtherboneRecord()
        record.reads = EtherboneReads(addrs=[addr+4*j for j in range(length_int)])
        record.rcount = len(record.reads)

        packet = EtherbonePacket()
        packet.records = [record]
        packet.encode()

        self.socket.sendto(bytes(packet), (self.server, self.port))

        datas, dummy = self.socket.recvfrom(8192)
        packet = EtherbonePacket(datas)
        packet.decode()
        datas = packet.records.pop().writes.get_datas()
        if self.debug:
            for i, value in enumerate(datas):
                print("read {:08x} @ {:08x}".format(value, addr + 4*i))
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

        self.socket.sendto(bytes(packet), (self.server, self.port))

        if self.debug:
            for i, value in enumerate(datas):
                print("write {:08x} @ {:08x}".format(value, addr + 4*i))
