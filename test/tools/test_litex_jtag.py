#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
from types import SimpleNamespace

from litex.tools.litex_jtag import JTAGRemoteBitbang


class Register:
    def __init__(self, value):
        self.value  = value
        self.writes = []

    def read(self):
        return self.value

    def write(self, value):
        self.value = value
        self.writes.append(value)


class Connection:
    def __init__(self, chunks):
        self.chunks = iter(chunks)
        self.output = bytearray()

    def recv(self, size):
        return next(self.chunks, b"")

    def sendall(self, data):
        self.output.extend(data)


class TestJTAGRemoteBitbang(unittest.TestCase):
    def setUp(self):
        self.control = Register(0xa)
        self.status  = Register(0)
        bus = SimpleNamespace(regs=SimpleNamespace(
            cpu_jtag_debug_control=self.control,
            cpu_jtag_debug_status=self.status,
        ))
        self.jtag = JTAGRemoteBitbang(bus)

    def test_jtag_pin_encoding(self):
        for command in b"01234567":
            self.jtag.process(command)
        self.assertEqual(self.control.writes, [8, 12, 10, 14, 9, 13, 11, 15])

    def test_trst_polarity_and_hold_during_scan(self):
        for command in b"t07r":
            self.jtag.process(command)
        self.assertEqual(self.control.writes, [2, 0, 7, 15])

    def test_tdo_responses(self):
        self.assertEqual(self.jtag.process(ord("R")), b"0")
        self.status.value = 1
        self.assertEqual(self.jtag.process(ord("R")), b"1")

    def test_fragmented_commands_and_quit(self):
        connection = Connection([b"t0", b"Rr", b"7RQ0"])
        self.jtag.serve(connection)
        self.assertEqual(connection.output, b"00")
        self.assertEqual(self.control.writes, [2, 0, 8, 15])

    def test_disconnect_and_activity_led(self):
        self.jtag.serve(Connection([b"Bb", b""]))
        self.assertEqual(self.control.writes, [])

    def test_unsupported_requests_do_not_change_pins(self):
        for command in b"suOc?":
            with self.subTest(command=command), self.assertRaises(ValueError):
                self.jtag.process(command)
        self.assertEqual(self.control.writes, [])
