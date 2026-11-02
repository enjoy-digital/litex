#
# This file is part of LiteX.
#
# Copyright (c) 2026 Enjoy-Digital <enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import time
import socket
import struct
import unittest
from unittest import mock

from litex.tools import litex_server


class TestServerCLI(unittest.TestCase):
    def test_jtag_stream_port_selection(self):
        # Two board servers need separate OpenOCD stream ports as well as
        # separate public Etherbone ports. Preserve the single-board default.
        for arguments, expected in (([], 20000), (["--jtag-port", "20001"], 20001)):
            with self.subTest(arguments=arguments):
                with mock.patch("sys.argv", ["litex_server", "--jtag", "--bind-port", "1235"] + arguments), \
                     mock.patch("litex.tools.litex_term.JTAGUART") as uart, \
                     mock.patch("litex.tools.remote.comm_uart.CommUART"), \
                     mock.patch("litex.tools.litex_server.os.ttyname", return_value="/dev/pts/test"), \
                     mock.patch("litex.tools.litex_server.RemoteServer") as server, \
                     mock.patch("time.sleep", side_effect=KeyboardInterrupt):
                    litex_server.main()
                    self.assertEqual(uart.call_args.kwargs["port"], expected)
                    self.assertEqual(server.call_args.args[2], 1235)
                    server.return_value.close.assert_called_once()
                    uart.return_value.close.assert_called_once()


# Test Server Port ---------------------------------------------------------------------------------

class _DummyComm:
    def open(self):
        pass

    def close(self):
        pass

class TestServerPort(unittest.TestCase):
    def test_port_not_shared(self):
        # A second server on the same port must fail instead of silently sharing the clients
        # between two bridges; the port must be reusable as soon as the first server is closed.
        first = litex_server.RemoteServer(_DummyComm(), "localhost", 0)
        first.open()
        port = first.socket.getsockname()[1]
        try:
            second = litex_server.RemoteServer(_DummyComm(), "localhost", port)
            with self.assertRaises(OSError):
                second.open()
        finally:
            first.close()
        third = litex_server.RemoteServer(_DummyComm(), "localhost", port)
        third.open()
        third.close()

# Test Server Robustness ---------------------------------------------------------------------------

class _SlowComm:
    """Comm stand-in answering reads after a delay, so a client can leave before the response."""
    def open(self):
        pass

    def close(self):
        pass

    def write(self, addr, datas):
        pass

    def read(self, addr, length=None, burst="incr"):
        time.sleep(0.2)
        return [0x12345678]*(1 if length is None else length)

class TestServerRobustness(unittest.TestCase):
    def test_client_gone_before_response(self):
        # A client closing (RST) before its read response must not stop the serving thread: the
        # next clients are still served (with one thread, the server used to stop after one).
        from litex.tools.litex_client import RemoteClient
        from litex.tools.remote.etherbone import EtherbonePacket, EtherboneRecord, EtherboneReads
        server = litex_server.RemoteServer(_SlowComm(), "localhost", 0)
        server.open()
        port = server.socket.getsockname()[1]
        server.start(1)
        try:
            for _ in range(3):
                s = socket.create_connection(("localhost", port), timeout=5)
                s.recv(128)
                record = EtherboneRecord(4)
                record.reads  = EtherboneReads(addr_size=4, addrs=[0x0])
                record.rcount = 1
                packet = EtherbonePacket(32)
                packet.records = [record]
                packet.encode()
                s.sendall(packet.bytes)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                s.close()
                time.sleep(0.3)
            with RemoteClient(port=port, raise_on_timeout=True, timeout=5) as bus:
                self.assertEqual(bus.read(0x0), 0x12345678)
        finally:
            server.close()

if __name__ == "__main__":
    unittest.main()
