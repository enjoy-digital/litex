#
# This file is part of LiteX.
#
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2017 Tim Ansell <mithro@mithis.com>
# SPDX-License-Identifier: BSD-2-Clause

import math
import struct

from litex.soc.interconnect.packet import HeaderField, Header

# Etherbone Constants / Headers / Helpers ----------------------------------------------------------

etherbone_magic                = 0x4e6f
etherbone_version              = 1
etherbone_packet_header_length = 8
etherbone_packet_header_fields = {
    "magic":     HeaderField(0,  0, 16),

    "version":   HeaderField(2,  4, 4),
    "nr":        HeaderField(2,  2, 1), # No Reads
    "pr":        HeaderField(2,  1, 1), # Probe Reply
    "pf":        HeaderField(2,  0, 1), # Probe Flag

    "addr_size": HeaderField(3,  4, 4), # 1=8bits, 2=16bits, 4=32bits, 8=64bits
    "port_size": HeaderField(3,  0, 4), # Same as above
}
etherbone_packet_header = Header(
    fields           = etherbone_packet_header_fields,
    length           = etherbone_packet_header_length,
    swap_field_bytes = True)


etherbone_record_header_length = 4
etherbone_record_header_fields = {
    "bca":         HeaderField(0,  0, 1), # ReplyToCfgSpace  - ??? (C)onfig (A)dress
    "rca":         HeaderField(0,  1, 1), # ReadFromCfgSpace - (R)ead from (C)onfig (A)dress
    "rff":         HeaderField(0,  2, 1), # ReadFIFO         - (R)ead (F)I(F)O
    "cyc":         HeaderField(0,  4, 1), # DropCycle        - Drop(Cyc)le
    "wca":         HeaderField(0,  5, 1), # WriteToCfgSpace  - (W)rite to (C)onfig (A)dress
    "wff":         HeaderField(0,  6, 1), # WriteFIFO        - (W)rite (F)I(F)O

    "byte_enable": HeaderField(1,  0, 8), # Select

    "wcount":      HeaderField(2,  0, 8), # Writes

    "rcount":      HeaderField(3,  0, 8), # Reads
}
etherbone_record_header = Header(
    fields           = etherbone_record_header_fields,
    length           = etherbone_record_header_length,
    swap_field_bytes = True)


def get_field_data(field, datas):
    v = int.from_bytes(datas[field.byte:field.byte+math.ceil(field.width/8)], "big")
    return (v >> field.offset) & (2**field.width-1)

pack_to_uint32 = struct.Struct('>I').pack
unpack_uint32_from = struct.Struct('>I').unpack

# Packet -------------------------------------------------------------------------------------------

class Packet(list):
    def __init__(self, init=[]):
        self.ongoing = False
        self.done    = False
        self.bytes   = init

# Etherbone Write / Read ---------------------------------------------------------------------------

class EtherboneWrite:
    def __init__(self, data):
        self.data = data

    def __repr__(self):
        return "WR32 0x{:08x}".format(self.data)


class EtherboneRead:
    def __init__(self, addr):
        self.addr = addr

    def __repr__(self):
        return "RD32 @ 0x{:08x}".format(self.addr)

# Etherbone Writes ---------------------------------------------------------------------------------

class EtherboneWrites(Packet):
    def __init__(self, init=[], base_addr=0, datas=[]):
        if isinstance(datas, list) and len(datas) > 255:
            raise ValueError(f"Burst size of {len(datas)} exceeds maximum of 255 allowed by Etherbone.")
        Packet.__init__(self, init)
        self.base_addr = base_addr
        self.writes    = []
        self.encoded   = init != []
        for data in datas:
            self.add(EtherboneWrite(data))

    def add(self, write):
        self.writes.append(write)

    def get_datas(self):
        datas = []
        for write in self.writes:
            datas.append(write.data)
        return datas

    def encode(self):
        if self.encoded:
            raise ValueError
        ba = bytearray()
        ba += pack_to_uint32(self.base_addr)
        for write in self.writes:
            ba += pack_to_uint32(write.data)
        self.bytes   = ba
        self.encoded = True

    def decode(self):
        if not self.encoded:
            raise ValueError
        ba = self.bytes
        self.base_addr = unpack_uint32_from(ba[:4])[0]
        writes = []
        offset = 4
        length = len(ba)
        while length > offset:
            writes.append(EtherboneWrite(unpack_uint32_from(ba[offset:offset+4])[0]))
            offset += 4
        self.writes  = writes
        self.encoded = False

    def __repr__(self):
        r = "Writes\n"
        r += "--------\n"
        r += "BaseAddr @ 0x{:08x}\n".format(self.base_addr)
        for write in self.writes:
            r += write.__repr__() + "\n"
        return r

# Etherbone Reads ----------------------------------------------------------------------------------

class EtherboneReads(Packet):
    def __init__(self, init=[], base_ret_addr=0, addrs=[]):
        if isinstance(addrs, list) and len(addrs) > 255:
            raise ValueError(f"Burst size of {len(addrs)} exceeds maximum of 255 allowed by Etherbone.")
        Packet.__init__(self, init)
        self.base_ret_addr = base_ret_addr
        self.reads   = []
        self.encoded = init != []
        for addr in addrs:
            self.add(EtherboneRead(addr))

    def add(self, read):
        self.reads.append(read)

    def get_addrs(self):
        addrs = []
        for read in self.reads:
            addrs.append(read.addr)
        return addrs

    def encode(self):
        if self.encoded:
            raise ValueError
        ba = bytearray()
        ba += pack_to_uint32(self.base_ret_addr)
        for read in self.reads:
            ba += pack_to_uint32(read.addr)
        self.bytes   = ba
        self.encoded = True

    def decode(self):
        if not self.encoded:
            raise ValueError
        ba = self.bytes
        base_ret_addr = unpack_uint32_from(ba[:4])[0]
        reads  = []
        offset = 4
        length = len(ba)
        while length > offset:
            reads.append(EtherboneRead(unpack_uint32_from(ba[offset:offset+4])[0]))
            offset += 4
        self.reads   = reads
        self.encoded = False

    def __repr__(self):
        r = "Reads\n"
        r += "--------\n"
        r += "BaseRetAddr @ 0x{:08x}\n".format(self.base_ret_addr)
        for read in self.reads:
            r += read.__repr__() + "\n"
        return r

# Etherbone Record ---------------------------------------------------------------------------------

class EtherboneRecord(Packet):
    def __init__(self, init=[]):
        Packet.__init__(self, init)
        self.writes      = None
        self.reads       = None
        self.bca         = 0
        self.rca         = 0
        self.rff         = 0
        self.cyc         = 0
        self.wca         = 0
        self.wff         = 0
        self.byte_enable = 0xf
        self.wcount      = 0
        self.rcount      = 0
        self.encoded     = init != []

    def decode(self):
        if not self.encoded:
            raise ValueError

        # Decode header
        header = list(self.bytes[:etherbone_record_header.length])
        for k, v in sorted(etherbone_record_header.fields.items()):
            setattr(self, k, get_field_data(v, header))
        offset = etherbone_record_header.length

        # Decode writes
        if self.wcount:
            self.writes = EtherboneWrites(self.bytes[offset:offset + 4*(self.wcount+1)])
            offset += 4*(self.wcount+1)
            self.writes.decode()

        # Decode reads
        if self.rcount:
            self.reads = EtherboneReads(self.bytes[offset:offset + 4*(self.rcount+1)])
            offset += 4*(self.rcount+1)
            self.reads.decode()

        self.encoded = False

    def encode(self):
        if self.encoded:
            raise ValueError

        # Set writes/reads count
        self.wcount = 0 if self.writes is None else len(self.writes.writes)
        self.rcount = 0 if self.reads  is None else len(self.reads.reads)

        ba = bytearray()

        # Encode header
        header = 0
        for k, v in sorted(etherbone_record_header.fields.items()):
            value = int.from_bytes(getattr(self, k).to_bytes(math.ceil(v.width/8), "big"), "little")
            header += (value << v.offset+(v.byte*8))
        ba += header.to_bytes(etherbone_record_header.length, "little")

        # Encode writes
        if self.wcount:
            self.writes.encode()
            ba += self.writes.bytes

        # Encode reads
        if self.rcount:
            self.reads.encode()
            ba += self.reads.bytes

        self.bytes   = ba
        self.encoded = True

    def __repr__(self, n=0):
        r = "Record {}\n".format(n)
        r += "--------\n"
        if self.encoded:
            for d in self.bytes:
                r += "{:02x}".format(d)
        else:
            for k in sorted(etherbone_record_header.fields.keys()):
                r += k + " : 0x{:0x}\n".format(getattr(self, k))
            if self.wcount:
                r += self.writes.__repr__()
            if self.rcount:
                r += self.reads.__repr__()
        return r

# Etherbone Packet ---------------------------------------------------------------------------------

class EtherbonePacket(Packet):
    def __init__(self, init=[]):
        Packet.__init__(self, init)
        self.encoded = init != []
        self.records = []

        self.magic     = etherbone_magic
        self.version   = etherbone_version
        self.addr_size = 32//8
        self.port_size = 32//8
        self.nr        = 0
        self.pr        = 0
        self.pf        = 0

    def decode(self):
        if not self.encoded:
            raise ValueError

        ba = self.bytes

        # Decode header
        header = list(ba[:etherbone_packet_header.length])
        for k, v in sorted(etherbone_packet_header.fields.items()):
            setattr(self, k, get_field_data(v, header))
        offset = etherbone_packet_header.length

        # Decode records
        length = len(ba)
        while length > offset:
            record = EtherboneRecord(ba[offset:])
            record.decode()
            self.records.append(record)
            offset += etherbone_record_header.length
            if record.wcount:
                offset += 4*(record.wcount + 1)
            if record.rcount:
                offset += 4*(record.rcount + 1)

        self.encoded = False

    def encode(self):
        if self.encoded:
            raise ValueError

        ba = bytearray()

        # Encode header
        header = 0
        for k, v in sorted(etherbone_packet_header.fields.items()):
            value = int.from_bytes(getattr(self, k).to_bytes(math.ceil(v.width/8), "big"), "little")
            header += (value << v.offset+(v.byte*8))
        ba += header.to_bytes(etherbone_packet_header.length, "little")

        # Encode records
        for record in self.records:
            record.encode()
            ba += record.bytes

        self.bytes   = ba
        self.encoded = True

    def __repr__(self):
        r = "Packet\n"
        r += "--------\n"
        if self.encoded:
            for d in self.bytes:
                r += "{:02x}".format(d)
        else:
            for k in sorted(etherbone_packet_header.fields.keys()):
                r += k + " : 0x{:0x}\n".format(getattr(self, k))
            for i, record in enumerate(self.records):
                r += record.__repr__(i)
        return r

# Etherbone IPC ------------------------------------------------------------------------------------

class EtherboneIPC:
    def send_packet(self, socket, packet):
        socket.sendall(packet.bytes)

    def receive_packet(self, socket):
        header_length = etherbone_packet_header_length + etherbone_record_header_length
        packet        = bytes()
        while len(packet) < header_length:
            chunk = socket.recv(header_length - len(packet))
            if len(chunk) == 0:
                return 0
            else:
                packet += chunk
        wcount, rcount = struct.unpack(">BB", packet[header_length-2:])
        counts = wcount + rcount
        packet_size = header_length + 4*(counts + 1)
        while len(packet) < packet_size:
            chunk = socket.recv(packet_size - len(packet))
            if len(chunk) == 0:
                return 0
            else:
                packet += chunk
        return packet
