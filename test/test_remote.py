#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import socket
import tempfile
import threading
import unittest
from unittest import mock

from litex.tools.litex_server import RemoteServer, _read_merger
from litex.tools.remote.etherbone import Packet
from litex.tools.remote.etherbone import EtherboneIPC
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


class FailingInfoSocket:
    def __init__(self):
        self.closed = False
        self.timeout = None

    def settimeout(self, timeout):
        self.timeout = timeout

    def recv(self, length):
        raise RuntimeError("server info failed")

    def close(self):
        self.closed = True


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


class TestReadMerger(unittest.TestCase):
    @staticmethod
    def _expand(reads):
        addrs = []
        for base, length, burst in reads:
            if burst == "fixed":
                addrs += [base] * length
            else:
                addrs += [base + 4*i for i in range(length)]
        return addrs

    def test_empty_reads(self):
        self.assertEqual(list(_read_merger([])), [])

    def test_incr_reads(self):
        addrs = [0x00, 0x04, 0x08]
        reads = list(_read_merger(addrs))

        self.assertEqual(reads, [(0x00, 3, "incr")])
        self.assertEqual(self._expand(reads), addrs)

    def test_fixed_reads(self):
        addrs = [0x20, 0x20, 0x20]
        reads = list(_read_merger(addrs))

        self.assertEqual(reads, [(0x20, 3, "fixed")])
        self.assertEqual(self._expand(reads), addrs)

    def test_mixed_reads_preserve_order(self):
        addrs = [0x00, 0x04, 0x04, 0x08, 0x20, 0x20]
        reads = list(_read_merger(addrs))

        self.assertEqual(reads, [(0x00, 2, "incr"), (0x04, 2, "incr"), (0x20, 2, "fixed")])
        self.assertEqual(self._expand(reads), addrs)

    def test_fixed_disabled_preserves_repeated_reads(self):
        addrs = [0x20, 0x20]
        reads = list(_read_merger(addrs, bursts=["incr"]))

        self.assertEqual(reads, [(0x20, 1, "incr"), (0x20, 1, "incr")])
        self.assertEqual(self._expand(reads), addrs)

    def test_max_length_splits_reads(self):
        addrs = [4*i for i in range(5)]
        reads = list(_read_merger(addrs, max_length=2))

        self.assertEqual(reads, [(0x00, 2, "incr"), (0x08, 2, "incr"), (0x10, 1, "incr")])
        self.assertEqual(self._expand(reads), addrs)

    def test_default_max_length_is_etherbone_safe(self):
        addrs = [4*i for i in range(256)]
        reads = list(_read_merger(addrs))

        self.assertEqual(reads, [(0x00, 255, "incr"), (0x3fc, 1, "incr")])
        self.assertEqual(self._expand(reads), addrs)

    def test_invalid_configuration(self):
        with self.assertRaises(ValueError):
            list(_read_merger([0], max_length=0))

        with self.assertRaises(ValueError):
            list(_read_merger([0], bursts=["fixed"]))

        with self.assertRaises(ValueError):
            list(_read_merger([0], bursts=["incr", "wrap"]))


class TestRemoteServer(unittest.TestCase):
    def test_uart_capabilities_are_cached(self):
        class CommUART:
            pass

        server = RemoteServer(CommUART(), "localhost", addr_width=64)

        self.assertEqual(server.addr_size, 8)
        self.assertEqual(server.read_max_length, 255)
        self.assertEqual(server.read_bursts, ["incr", "fixed"])
        self.assertTrue(server.lock.acquire(blocking=False))
        server.lock.release()

    def test_default_capabilities_are_cached(self):
        class CommUSB:
            pass

        server = RemoteServer(CommUSB(), "localhost")

        self.assertEqual(server.addr_size, 4)
        self.assertEqual(server.read_max_length, 1)
        self.assertEqual(server.read_bursts, ["incr"])


class TestRemoteClient(unittest.TestCase):
    def _client(self, **kwargs):
        with mock.patch("litex.tools.litex_client.os.path.exists", return_value=False):
            return RemoteClient(**kwargs)

    def test_csr_csv_sets_widths_and_registers(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("constant,config_csr_data_width,32,,\n")
            f.write("constant,config_bus_address_width,64,,\n")
            f.write("csr_base,ctrl,0xe0000000,,\n")
            f.write("csr_register,ctrl_reset,0xe0000000,1,rw\n")
            f.write("memory_region,csr,0xe0000000,65536,io\n")
            csr_csv = f.name
        self.addCleanup(lambda: os.path.exists(csr_csv) and os.unlink(csr_csv))

        bus = RemoteClient(csr_csv=csr_csv, csr_data_width=32, csr_bus_address_width=64)

        self.assertEqual(bus.csr_data_width, 32)
        self.assertEqual(bus.csr_bus_address_width, 64)
        self.assertEqual(bus.bases.ctrl, 0xe0000000)
        self.assertEqual(bus.regs.ctrl_reset.addr, 0xe0000000)
        self.assertEqual(bus.mems.csr.base, 0xe0000000)

    def test_csr_csv_rejects_mismatched_bus_address_width(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("constant,config_csr_data_width,32,,\n")
            f.write("constant,config_bus_address_width,32,,\n")
            csr_csv = f.name
        self.addCleanup(lambda: os.path.exists(csr_csv) and os.unlink(csr_csv))

        with self.assertRaises(KeyError):
            RemoteClient(csr_csv=csr_csv, csr_bus_address_width=64)

    def test_explicit_widths_without_csr_csv(self):
        bus = self._client(csr_data_width=8, csr_bus_address_width=64)

        self.assertEqual(bus.csr_data_width, 8)
        self.assertEqual(bus.csr_bus_address_width, 64)

    def test_open_passes_timeout_and_cleans_up_on_info_error(self):
        bus = self._client(timeout=3.5)
        fake_socket = FailingInfoSocket()

        with mock.patch("litex.tools.litex_client.socket.create_connection", return_value=fake_socket) as create_connection:
            with self.assertRaisesRegex(RuntimeError, "server info failed"):
                bus.open()

        create_connection.assert_called_once_with(("localhost", 1234), timeout=3.5)
        self.assertEqual(fake_socket.timeout, 3.5)
        self.assertTrue(fake_socket.closed)
        self.assertFalse(hasattr(bus, "socket"))
        self.assertFalse(bus.binded)

    def test_pcie_server_info_without_csr_metadata(self):
        bus = self._client(base_address=0x1000)
        bus.socket = mock.Mock()
        bus.socket.recv.return_value = b"CommPCIe:localhost:1234"

        bus._receive_server_info()

        self.assertEqual(bus.base_address, 0x1000)

    def test_pcie_server_info_translates_csr_base(self):
        bus = self._client(base_address=0x1000)
        bus.socket = mock.Mock()
        bus.socket.recv.return_value = b"CommPCIe:localhost:1234"
        bus.mems = mock.Mock()
        bus.mems.csr.base = 0xe0000000

        bus._receive_server_info()

        self.assertEqual(bus.base_address, -0xe0000000)

    def test_base_address_is_added_to_requests(self):
        bus = self._client(base_address=0x10000000)
        bus.socket = object()
        sent = []

        bus.send_packet    = lambda socket, packet: sent.append(packet.bytes)
        bus.receive_packet = lambda socket, addr_size: _read_response([0x12345678])

        self.assertEqual(bus.read(0x20), 0x12345678)
        self.assertEqual(_decode_read_addrs(sent[0]), [0x10000020])

        sent.clear()
        bus.write(0x40, 0x5a5a5a5a)
        self.assertEqual(_decode_write(sent[0]), (0x10000040, [0x5a5a5a5a]))

    def test_read_uses_socket_send_and_receive_path(self):
        bus = self._client()
        client_socket, server_socket = socket.socketpair()
        self.addCleanup(client_socket.close)
        self.addCleanup(server_socket.close)
        bus.socket = client_socket
        bus.socket.settimeout(1.0)
        server_socket.settimeout(1.0)
        observed_addrs = []

        def server():
            request = EtherboneIPC().receive_packet(server_socket, addr_size=4)
            observed_addrs.extend(_decode_read_addrs(request))
            server_socket.sendall(_read_response([0xaa, 0xbb, 0xcc]))

        server_thread = threading.Thread(target=server)
        server_thread.start()

        self.assertEqual(bus.read(0x8000, length=3), [0xaa, 0xbb, 0xcc])
        server_thread.join(timeout=1.0)

        self.assertFalse(server_thread.is_alive())
        self.assertEqual(observed_addrs, [0x8000, 0x8004, 0x8008])

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
        FakeRemoteClient.read_datas = []

    def test_read_memory_uses_burst_and_trims_file(self):
        FakeRemoteClient.read_datas = [0x11223344, 0x55667788]
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))

        with mock.patch("litex.tools.litex_client.RemoteClient", FakeRemoteClient):
            read_memory("host", "csr.csv", 1234, 0x6000, length=6, file=path, endianness="big")

        bus = FakeRemoteClient.instances[0]
        self.assertEqual(bus.read_calls, [(0x6000, 2, "incr")])
        self.assertEqual(bus.kwargs["timeout"], 2.0)
        self.assertFalse(bus.kwargs["raise_on_timeout"])
        with open(path, "rb") as f:
            self.assertEqual(f.read(), b"\x11\x22\x33\x44\x55\x66")

    def test_read_memory_zero_length_does_not_read_bus(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))

        with mock.patch("litex.tools.litex_client.RemoteClient", FakeRemoteClient):
            read_memory("host", "csr.csv", 1234, 0x6000, length=0, file=path, timeout=4.0, raise_on_timeout=True)

        bus = FakeRemoteClient.instances[0]
        self.assertEqual(bus.read_calls, [])
        self.assertEqual(bus.kwargs["timeout"], 4.0)
        self.assertTrue(bus.kwargs["raise_on_timeout"])
        with open(path, "rb") as f:
            self.assertEqual(f.read(), b"")

    def test_write_memory_uses_burst_and_pads_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"\x01\x02\x03\x04\x05")
            path = f.name
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))

        with mock.patch("litex.tools.litex_client.RemoteClient", FakeRemoteClient):
            write_memory("host", "csr.csv", 1234, 0x7000, data=0, file=path, length=None, endianness="big")

        bus = FakeRemoteClient.instances[0]
        self.assertEqual(bus.write_calls, [(0x7000, [0x01020304, 0x05000000], "incr")])

    def test_write_memory_empty_file_does_not_write_bus(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))

        with mock.patch("litex.tools.litex_client.RemoteClient", FakeRemoteClient):
            write_memory("host", "csr.csv", 1234, 0x7000, data=0, file=path, length=None)

        bus = FakeRemoteClient.instances[0]
        self.assertEqual(bus.write_calls, [])


if __name__ == "__main__":
    unittest.main()
