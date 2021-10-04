#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.icap import *


class TestICAP(unittest.TestCase):
    def test_icap_command_reload(self):
        def generator(dut):
            yield dut.addr.eq(ICAPRegisters.CMD)
            yield dut.data.eq(ICAPCMDs.IPROG)
            for i in range(16):
                yield
            yield dut.send.eq(1)
            yield
            yield dut.send.eq(0)
            for i in range(32):
                print(f"{(yield dut._i):08x}")
                yield

        dut = ICAP(with_csr=False, simulation=True)
        clocks = {"sys": 10, "icap": 10}
        run_simulation(dut, generator(dut), clocks, vcd_name="icap.vcd")

    def test_icap_bitstream_syntax(self):
        dut = ICAPBitstream(simulation=True)
