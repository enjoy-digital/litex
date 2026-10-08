#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *
from migen.fhdl.specials import Tristate

from litex.gen import *

from litex.soc.cores.ram.gowin_hyperram import GowinHyperRAM
from litex.soc.integration.export import get_csr_header
from litex.soc.integration.soc import SoCCSRRegion
from litex.soc.interconnect.csr_bus import CSRBankArray


class _Pads:
    def __init__(self, data_width=16, nchips=1):
        self.clk    = Signal(nchips)
        self.clk_n  = Signal(nchips)
        self.cs_n   = Signal(nchips)
        self.rst_n  = Signal(nchips)
        self.dq     = Signal(data_width*nchips)
        self.rwds   = Signal((data_width//8)*nchips)


class _DUT(LiteXModule):
    def __init__(self, **kwargs):
        self.cd_sys4x = ClockDomain()
        self.hyperram = GowinHyperRAM(_Pads(), sys_clk_freq=27e6, clk_ratio="4:1", **kwargs)


class TestGowinHyperRAM(unittest.TestCase):
    def test_wrapper_creates_tristates(self):
        dut = _DUT()
        fragment = dut.get_fragment()
        tristates = [special for special in fragment.specials if isinstance(special, Tristate)]
        self.assertEqual(len(tristates), 2)

    def test_wrapper_csr_names(self):
        dut = _DUT()
        registers = {
            "config":      "write",
            "status":      "read",
            "reg_control": "write",
            "reg_status":  "read",
            "reg_wdata":   "write",
            "reg_rdata":   "read",
        }
        # Repeated discovery must keep names and register ordering stable.
        for sort in [False, True, False]:
            self.assertEqual(
                [csr.name for csr in dut.hyperram.get_csrs(sort=sort)],
                list(registers),
            )

        # Exercise the same CSR bank discovery and header export used by a SoC.
        banks = CSRBankArray(dut, lambda name, memory: 0, data_width=32)
        self.assertEqual(len(banks.banks), 1)
        name, csrs, _, _ = banks.banks[0]
        self.assertEqual(name, "hyperram")
        self.assertEqual([csr.name for csr in csrs], list(registers))
        header = get_csr_header(
            regions = {name: SoCCSRRegion(origin=0xf0000000, busword=32, obj=csrs)},
            constants = {},
        )
        for name, access in registers.items():
            self.assertIn(f"#define CSR_HYPERRAM_{name.upper()}_ADDR ", header)
            self.assertIn(f"hyperram_{name}_{access}(", header)
        self.assertIn("#define CSR_HYPERRAM_CONFIG_LATENCY_OFFSET 8", header)
        self.assertIn("#define CSR_HYPERRAM_STATUS_CLK_RATIO_OFFSET 1", header)

    def test_wrapper_without_csrs(self):
        dut = _DUT(with_csr=False)
        self.assertEqual(dut.hyperram.get_csrs(), [])
        banks = CSRBankArray(dut, lambda name, memory: 0, data_width=32)
        self.assertEqual(banks.banks, [])

    def test_wrapper_deferred_csrs(self):
        dut = _DUT(with_csr=False)
        self.assertEqual(dut.hyperram.get_csrs(), [])
        dut.hyperram.hyperram.add_csr()
        self.assertEqual(
            [csr.name for csr in dut.hyperram.get_csrs(sort=True)],
            ["config", "status", "reg_control", "reg_status", "reg_wdata", "reg_rdata"],
        )
        self.assertIs(dut.hyperram.bus, dut.hyperram.hyperram.bus)


if __name__ == "__main__":
    unittest.main()
