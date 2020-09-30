#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2016 Tim 'mithro' Ansell <mithro@mithis.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import socket

from litex.tools.remote.etherbone import EtherbonePacket, EtherboneRecord
from litex.tools.remote.etherbone import EtherboneReads, EtherboneWrites
from litex.tools.remote.etherbone import EtherboneIPC
from litex.tools.remote.csr_builder import CSRBuilder


class RemoteClient(EtherboneIPC, CSRBuilder):
    def __init__(self, host="localhost", port=1234, base_address=0, csr_csv=None, csr_data_width=None, debug=False):
        # If csr_csv set to None and local csr.csv file exists, use it.
        if csr_csv is None and os.path.exists("csr.csv"):
            csr_csv = "csr.csv"
        # If valid csr_csv file found, build the CSRs.
        if csr_csv is not None:
            CSRBuilder.__init__(self, self, csr_csv, csr_data_width)
        # Else if csr_data_width set to None, force to csr_data_width 32-bit.
        elif csr_data_width is None:
            csr_data_width = 32
        self.host         = host
        self.port         = port
        self.base_address = base_address
        self.debug        = debug

    def open(self):
        if hasattr(self, "socket"):
            return
        self.socket = socket.create_connection((self.host, self.port), 5.0)
        self.socket.settimeout(5.0)

    def close(self):
        if not hasattr(self, "socket"):
            return
        self.socket.close()
        del self.socket

    def read(self, addr, length=None, burst="incr"):
        length_int = 1 if length is None else length
        # prepare packet
        record = EtherboneRecord()
        incr = (burst == "incr")
        record.reads = EtherboneReads(addrs=[self.base_address + addr + 4*incr*j for j in range(length_int)])
        record.rcount = len(record.reads)

        # send packet
        packet = EtherbonePacket()
        packet.records = [record]
        packet.encode()
        self.send_packet(self.socket, packet[:])

        # receive response
        packet = EtherbonePacket(self.receive_packet(self.socket))
        packet.decode()
        datas = packet.records.pop().writes.get_datas()
        if self.debug:
            for i, data in enumerate(datas):
                print("read {:08x} @ {:08x}".format(data, self.base_address + addr + 4*i))
        return datas[0] if length is None else datas

    def write(self, addr, datas):
        datas = datas if isinstance(datas, list) else [datas]
        record = EtherboneRecord()
        record.writes = EtherboneWrites(base_addr=self.base_address + addr, datas=[d for d in datas])
        record.wcount = len(record.writes)

        packet = EtherbonePacket()
        packet.records = [record]
        packet.encode()
        self.send_packet(self.socket, packet)

        if self.debug:
            for i, data in enumerate(datas):
                print("write {:08x} @ {:08x}".format(data, self.base_address + addr + 4*i))
