#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.gen import LiteXModule
from litex.gen.fhdl.utils import get_signals


class TestFHDLUtils(unittest.TestCase):
    def test_get_signals_from_object(self):
        class DUT:
            def __init__(self):
                self.a        = Signal(name="a")
                self.b        = Signal(name="b")
                self.record   = Record([("c", 1), ("d", 2)])
                self.group    = [self.a, {"b": self.b}, (self.record,)]
                self._private = Signal(name="private")

        dut = DUT()

        self.assertEqual(get_signals(dut), [
            dut.a,
            dut.b,
            dut.record.c,
            dut.record.d,
        ])

    def test_get_signals_from_signal_record_and_containers(self):
        signal = Signal(name="signal")
        record = Record([("a", 1), ("b", 2)])

        self.assertEqual(get_signals(object()), [])
        self.assertEqual(get_signals(signal), [signal])
        self.assertEqual(get_signals(record), [record.a, record.b])
        self.assertEqual(get_signals([signal, record, {"again": signal}]), [
            signal,
            record.a,
            record.b,
        ])

    def test_get_signals_recurse(self):
        class Child(LiteXModule):
            def __init__(self, name):
                self.signal = Signal(name=name)

        class DUT(LiteXModule):
            def __init__(self):
                self.top_signal = Signal(name="top")
                self.child      = Child("child")
                self.submodules += Child("unnamed")

        dut = DUT()

        self.assertEqual(get_signals(dut), [
            dut.top_signal,
        ])
        self.assertEqual(get_signals(dut, recurse=True), [
            dut.top_signal,
            dut.child.signal,
            dut._submodules[1][1].signal,
        ])

    def test_get_signals_cycle(self):
        class Child(LiteXModule):
            def __init__(self):
                self.signal = Signal(name="child")

        class DUT(LiteXModule):
            def __init__(self):
                self.signal = Signal(name="top")
                self.child  = Child()
                self.child.parent = self

        dut = DUT()

        self.assertEqual(get_signals(dut, recurse=True), [
            dut.signal,
            dut.child.signal,
        ])

    def test_litex_module_get_signals(self):
        class DUT(LiteXModule):
            def __init__(self):
                self.signal = Signal(name="signal")

        dut = DUT()

        self.assertEqual(dut.get_signals(), [dut.signal])


if __name__ == "__main__":
    unittest.main()
