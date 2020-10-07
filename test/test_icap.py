#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.icap import ICAP, ICAPBitstream


class TestICAP(unittest.TestCase):
    def test_icap_command_reload(self):
        def generator(dut):
            yield dut.addr.eq(0x4)
            yield dut.data.eq(0xf)
            for i in range(16):
                yield
            yield dut.send.eq(1)
            yield
            yield dut.send.eq(0)
            for i in range(256):
                yield

        dut = ICAP(with_csr=False, simulation=True)
        clocks = {"sys": 10, "icap":20}
        run_simulation(dut, generator(dut), clocks, vcd_name="icap.vcd")

    def test_icap_bitstream_syntax(self):
        dut = ICAPBitstream(simulation=True)
