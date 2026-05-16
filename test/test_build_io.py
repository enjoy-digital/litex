import unittest

from migen import *

from litex.build.io import (
    DDRInput,
    DDROutput,
    DDRTristate,
    SDROutput,
    SDRTristate,
)
from litex.gen.fhdl import verilog


class TestBuildIO(unittest.TestCase):
    def test_inferred_sdrio_uses_separate_clock_domains(self):
        dut = Module()
        a    = Signal(2)
        b    = Signal(2)
        c    = Signal(2)
        d    = Signal(2)
        clk0 = Signal()
        clk1 = Signal()

        dut.specials += [
            SDROutput(a, b, clk0),
            SDROutput(c, d, clk1),
        ]

        v = str(verilog.convert(dut, ios={a, b, c, d, clk0, clk1}))
        self.assertEqual(v.count("always @(posedge "), 2)
        self.assertIn("b <= a;", v)
        self.assertIn("d <= c;", v)

    def test_sdr_tristate_width_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "SDRTristate signal widths"):
            SDRTristate(io=Signal(2), o=Signal(1), oe=Signal(1))

    def test_ddr_input_width_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "DDRInput signal widths"):
            DDRInput(i=Signal(2), o1=Signal(1), o2=Signal(2))

    def test_ddr_output_width_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "DDROutput signal widths"):
            DDROutput(i1=Signal(2), i2=Signal(2), o=Signal(1))

    def test_ddr_tristate_width_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "DDRTristate signal widths"):
            DDRTristate(io=Signal(2), o1=Signal(2), o2=Signal(2), oe1=Signal(1))

    def test_ddr_tristate_requires_paired_sync_inputs(self):
        with self.assertRaisesRegex(ValueError, "i1 and i2"):
            DDRTristate(
                io  = Signal(2),
                o1  = Signal(2),
                o2  = Signal(2),
                oe1 = Signal(2),
                i1  = Signal(2),
            )


if __name__ == "__main__":
    unittest.main()
