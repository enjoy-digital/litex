# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import unittest

from migen import *

from litex.soc.cores.icap import ICAP, ICAPBitstream


class TestICAP(unittest.TestCase):
    def test_icap_command_reload(self):
        def generator(dut):
            yield dut.addr.storage.eq(0x4)
            yield dut.data.storage.eq(0xf)
            for i in range(16):
                yield
            yield dut.send.re.eq(1)
            yield
            yield dut.send.re.eq(0)
            for i in range(256):
                yield

        dut = ICAP(simulation=True)
        clocks = {"sys": 10,
                  "icap":20}
        run_simulation(dut, generator(dut), clocks, vcd_name="icap.vcd")

    def test_icap_bitstream_syntax(self):
        dut = ICAPBitstream(simulation=True)
