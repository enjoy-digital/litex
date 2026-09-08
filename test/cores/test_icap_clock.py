#
# This file is part of LiteX.
#
# Copyright (c) 2026 Enjoy-Digital <enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import ClockDomain, ClockSignal, Module, Signal, run_simulation
from litex.soc.cores.icap import ICAP, ICAPCMDs, ICAPRegisters, ICAP_SYNC


class TestICAPClock(unittest.TestCase):
    def test_external_clock_removes_fabric_divider(self):
        external = Signal()
        dut = ICAP(with_csr=False, simulation=True, external_clock=external)
        fragment = dut.get_fragment()
        self.assertFalse(fragment.sync.get("sys", []))
        self.assertTrue(any(getattr(statement, "l", None) is dut.cd_icap.clk and
                            getattr(statement, "r", None) is external
                            for statement in fragment.comb))
        default = ICAP(with_csr=False, simulation=True).get_fragment()
        self.assertEqual(len(default.sync["sys"]), 2)

    def test_command_sequence_with_both_clock_sources(self):
        captures = []
        for external in (False, True):
            class DUT(Module):
                def __init__(self):
                    self.clock_domains.cd_input = ClockDomain("input")
                    self.submodules.icap = ICAP(with_csr=False, simulation=True,
                        external_clock=ClockSignal("input") if external else None)
            dut = DUT()
            words = []

            def stimulus():
                yield dut.icap.addr.eq(ICAPRegisters.CMD)
                yield dut.icap.write_data.eq(ICAPCMDs.IPROG)
                yield dut.icap.write.eq(1)
                for _ in range(400):
                    yield
                self.assertEqual((yield dut.icap.done), 1)

            def monitor():
                for _ in range(24):
                    if not (yield dut.icap._csib):
                        words.append((yield dut.icap._i))
                    yield

            run_simulation(dut, {"sys": stimulus(), "icap": monitor()},
                           clocks={"sys": 10, "icap": 160, "input": 160})
            self.assertIn(ICAP_SYNC, words)
            self.assertIn(ICAPCMDs.IPROG, words)
            captures.append(words)
        self.assertEqual(captures[0], captures[1])
