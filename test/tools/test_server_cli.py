#
# This file is part of LiteX.
#
# Copyright (c) 2026 Enjoy-Digital <enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

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

if __name__ == "__main__":
    unittest.main()
