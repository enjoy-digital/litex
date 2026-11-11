#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import io
import unittest
import contextlib
from unittest import mock

from litex.tools import litex_client
from litex.tools.remote.csr_builder import CSRElements, CSRRegister

# Fake Remote Client -------------------------------------------------------------------------------

class FakeClient:
    """RemoteClient stand-in: a scratch CSR and a LiteSPI master RX/TX CSR (read pops the RX FIFO)."""
    reads = []
    def __init__(self, **kwargs):
        regs = {
            "ctrl_scratch"         : 0xf0000004,
            "spiflash_master_rxtx" : 0xf0003000,
        }
        self.regs = CSRElements({name: CSRRegister(self.read, self.write, name, addr, 1, 32, "rw")
            for name, addr in regs.items()})

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, addr, length=None, burst="incr"):
        FakeClient.reads.append(addr)
        return 0x5a if length is None else [0x5a]*length

    def write(self, addr, datas, burst="incr"):
        pass

def _dump(filter=None):
    FakeClient.reads = []
    out = io.StringIO()
    with mock.patch("litex.tools.litex_client.RemoteClient", FakeClient), contextlib.redirect_stdout(out):
        registers = litex_client.dump_registers("localhost", None, 1234, filter=filter)
    return registers, FakeClient.reads, out.getvalue()

# Test LiteX Client Registers Dump -----------------------------------------------------------------

class TestLiteXClientRegs(unittest.TestCase):
    def test_regs_skips_read_side_effect_registers(self):
        for filter in [None, "spiflash"]:
            registers, reads, out = _dump(filter)
            self.assertNotIn(0xf0003000, reads)
            self.assertNotIn("spiflash_master_rxtx", [r["name"] for r in registers])
            self.assertIn("not read", out)

    def test_regs_reads_side_effect_register_named_exactly(self):
        registers, reads, out = _dump("spiflash_master_rxtx")
        self.assertEqual(reads, [0xf0003000])
        self.assertEqual(registers, [{"name": "spiflash_master_rxtx", "address": 0xf0003000, "value": 0x5a}])

if __name__ == "__main__":
    unittest.main()
