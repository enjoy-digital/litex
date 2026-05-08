#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import tempfile
import unittest
from unittest import mock

from litex.tools.remote.etherbone import Packet
from litex.tools.remote.etherbone import EtherbonePacket, EtherboneRecord
from litex.tools.remote.etherbone import EtherboneReads, EtherboneWrites
from litex.tools.litex_client import RemoteClient, read_memory, write_memory


def _read_response(datas, addr_width=32):
    addr_size = addr_width // 8
    record = EtherboneRecord(addr_size)
    record.writes = EtherboneWrites(addr_size=addr_size, datas=datas)

    packet = EtherbonePacket(addr_width)
    packet.records = [record]
    packet.encode()
    return packet.bytes


def _decode_read_addrs(packet_bytes, addr_width=32):
    packet = EtherbonePacket(addr_width, packet_bytes)
    packet.decode()
    return packet.records[0].reads.get_addrs()


def _decode_write(packet_bytes, addr_width=32):
    packet = EtherbonePacket(addr_width, packet_bytes)
    packet.decode()
    writes = packet.records[0].writes
    return writes.base_addr, writes.get_datas()


class TimeoutSocket:
    def recv(self, length):
        raise TimeoutError


class FakeRemoteClient:
    read_datas = []
    instances  = []

    def __init__(self, *args, **kwargs):
        self.args        = args
        self.kwargs      = kwargs
        self.read_calls  = []
        self.write_calls = []
        FakeRemoteClient.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, addr, length=None, burst="incr"):
        self.read_calls.append((addr, length, burst))
        return FakeRemoteClient.read_datas[:length]

    def write(self, addr, datas, burst="incr"):
        self.write_calls.append((addr, datas, burst))


class TestEtherboneHelpers(unittest.TestCase):
    def test_packet_default_bytes_are_independent(self):
        packet0 = Packet()
        packet0.bytes.append(0x5a)

        packet1 = Packet()
        self.assertEqual(packet1.bytes, [])

    def test_etherbone_burst_limit(self):
        with self.assertRaises(ValueError):
            EtherboneReads(addrs=list(range(256)))

        with self.assertRaises(ValueError):
            EtherboneWrites(datas=list(range(256)))

    def test_etherbone_packet_roundtrip(self):
        record = EtherboneRecord(addr_size=4)
        record.writes = EtherboneWrites(addr_size=4, base_addr=0x1000, datas=[0x12345678])
        record.reads  = EtherboneReads(addr_size=4, addrs=[0x2000, 0x2004])

        packet = EtherbonePacket(addr_width=32)
        packet.records = [record]
        packet.encode()

        decoded = EtherbonePacket(addr_width=32, init=packet.bytes)
        decoded.decode()

        self.assertEqual(decoded.records[0].writes.base_addr, 0x1000)
        self.assertEqual(decoded.records[0].writes.get_datas(), [0x12345678])
        self.assertEqual(decoded.records[0].reads.get_addrs(), [0x2000, 0x2004])


class TestRemoteClient(unittest.TestCase):
    def _client(self, **kwargs):
        with mock.patch("litex.tools.litex_client.os.path.exists", return_value=False):
            return RemoteClient(**kwargs)

    def test_explicit_widths_without_csr_csv(self):
        bus = self._client(csr_data_width=8, csr_bus_address_width=64)

        self.assertEqual(bus.csr_data_width, 8)
        self.assertEqual(bus.csr_bus_address_width, 64)

    def test_pcie_server_info_without_csr_metadata(self):
        bus = self._client(base_address=0x1000)
        bus.socket = mock.Mock()
        bus.socket.recv.return_value = b"CommPCIe:localhost:1234"

        bus._receive_server_info()

        self.assertEqual(bus.base_address, 0x1000)

    def test_read_is_split_into_etherbone_sized_chunks(self):
        bus = self._client()
        bus.socket = object()
        sent = []
        responses = [
            _read_response(list(range(255))),
            _read_response(list(range(255, 260))),
        ]

        bus.send_packet    = lambda socket, packet: sent.append(packet.bytes)
        bus.receive_packet = lambda socket, addr_size: responses.pop(0)

        datas = bus.read(0x1000, length=260)

        self.assertEqual(datas, list(range(260)))
        self.assertEqual(len(sent), 2)
        self.assertEqual(_decode_read_addrs(sent[0]), [0x1000 + 4*i for i in range(255)])
        self.assertEqual(_decode_read_addrs(sent[1]), [0x1000 + 4*i for i in range(255, 260)])

    def test_fixed_read_repeats_address(self):
        bus = self._client()
        bus.socket = object()
        sent = []

        bus.send_packet    = lambda socket, packet: sent.append(packet.bytes)
        bus.receive_packet = lambda socket, addr_size: _read_response([1, 2, 3])

        datas = bus.read(0x2000, length=3, burst="fixed")

        self.assertEqual(datas, [1, 2, 3])
        self.assertEqual(_decode_read_addrs(sent[0]), [0x2000, 0x2000, 0x2000])

    def test_write_is_split_into_etherbone_sized_chunks(self):
        bus = self._client()
        bus.socket = object()
        sent = []

        bus.send_packet = lambda socket, packet: sent.append(packet.bytes)
        bus.write(0x3000, list(range(260)))

        self.assertEqual(len(sent), 2)
        self.assertEqual(_decode_write(sent[0]), (0x3000, list(range(255))))
        self.assertEqual(_decode_write(sent[1]), (0x3000 + 4*255, list(range(255, 260))))

    def test_fixed_write_uses_single_word_packets(self):
        bus = self._client()
        bus.socket = object()
        sent = []

        bus.send_packet = lambda socket, packet: sent.append(packet.bytes)
        bus.write(0x4000, [0x11, 0x22], burst="fixed")

        self.assertEqual(len(sent), 2)
        self.assertEqual(_decode_write(sent[0]), (0x4000, [0x11]))
        self.assertEqual(_decode_write(sent[1]), (0x4000, [0x22]))

    def test_default_timeout_returns_zeroes(self):
        bus = self._client()
        bus.socket = TimeoutSocket()

        bus.send_packet    = lambda socket, packet: None
        bus.receive_packet = lambda socket, addr_size: 0

        self.assertEqual(bus.read(0x5000, length=3), [0, 0, 0])

    def test_strict_timeout_raises(self):
        bus = self._client(raise_on_timeout=True)
        bus.socket = TimeoutSocket()

        bus.send_packet    = lambda socket, packet: None
        bus.receive_packet = lambda socket, addr_size: 0

        with self.assertRaises(TimeoutError):
            bus.read(0x5000, length=3)

    def test_invalid_burst_raises(self):
        bus = self._client()

        with self.assertRaises(ValueError):
            bus.read(0, burst="wrap")

        with self.assertRaises(ValueError):
            bus.write(0, 0, burst="wrap")


class TestLiteXClientUtilities(unittest.TestCase):
    def setUp(self):
        FakeRemoteClient.instances = []

    def test_read_memory_uses_burst_and_trims_file(self):
        FakeRemoteClient.read_datas = [0x11223344, 0x55667788]
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))

        with mock.patch("litex.tools.litex_client.RemoteClient", FakeRemoteClient):
            read_memory("host", "csr.csv", 1234, 0x6000, length=6, file=path, endianness="big")

        bus = FakeRemoteClient.instances[0]
        self.assertEqual(bus.read_calls, [(0x6000, 2, "incr")])
        with open(path, "rb") as f:
            self.assertEqual(f.read(), b"\x11\x22\x33\x44\x55\x66")

    def test_write_memory_uses_burst_and_pads_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"\x01\x02\x03\x04\x05")
            path = f.name
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))

        with mock.patch("litex.tools.litex_client.RemoteClient", FakeRemoteClient):
            write_memory("host", "csr.csv", 1234, 0x7000, data=0, file=path, length=None, endianness="big")

        bus = FakeRemoteClient.instances[0]
        self.assertEqual(bus.write_calls, [(0x7000, [0x01020304, 0x05000000], "incr")])


if __name__ == "__main__":
    unittest.main()
