import unittest

from migen import *

from litex.build.efinix.common import EfinixTrionDDRTristateImpl
from litex.build.gowin.common import gowin_special_overrides
from litex.build.io import (
    ClkOutput,
    DDRInput,
    DDROutput,
    DDRTristate,
    DifferentialInput,
    DifferentialOutput,
    SDROutput,
    SDRTristate,
)
from litex.build.lattice.common import lattice_NX_special_overrides
from litex.build.xilinx.platform import XilinxUSPlatform
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

    def test_xilinx_ultrascale_xcvu_uses_us_overrides(self):
        platform = XilinxUSPlatform("xcvu9p-flga2104-2-i", [], toolchain="vivado")
        dut = Module()
        i1  = Signal()
        i2  = Signal()
        o   = Signal()
        clk = Signal()

        dut.specials += DDROutput(i1, i2, o, clk)

        v = str(platform.get_verilog(dut, ios={i1, i2, o, clk}))
        self.assertIn("ODDRE1", v)

    def test_gowin_ddr_primitives_are_lowered_per_bit(self):
        dut = Module()
        i   = Signal(4)
        o1  = Signal(4)
        o2  = Signal(4)
        i1  = Signal(4)
        i2  = Signal(4)
        o   = Signal(4)
        clk = Signal()

        dut.specials += [
            DDRInput(i, o1, o2, clk),
            DDROutput(i1, i2, o, clk),
        ]

        v = str(verilog.convert(
            dut,
            ios               = {i, o1, o2, i1, i2, o, clk},
            special_overrides = gowin_special_overrides,
        ))
        self.assertEqual(v.count("\nIDDR IDDR"), 4)
        self.assertEqual(v.count("\nODDR ODDR"), 4)

    def test_lattice_nx_ddr_tristate_preserves_i_async(self):
        dut = Module()
        io      = Signal(2)
        o1      = Signal(2)
        o2      = Signal(2)
        oe      = Signal(2)
        i_async = Signal(2)
        clk     = Signal()

        dut.specials += DDRTristate(io, o1, o2, oe, clk=clk, i_async=i_async)

        v = str(verilog.convert(
            dut,
            ios               = {io, o1, o2, oe, i_async, clk},
            special_overrides = lattice_NX_special_overrides,
        ))
        self.assertIn("output wire    [1:0] i_async", v)
        self.assertIn("assign i_async =", v)

    def test_efinix_ddr_tristate_rejects_i_async_with_registered_inputs(self):
        with self.assertRaisesRegex(ValueError, "i_async"):
            EfinixTrionDDRTristateImpl(
                io      = Signal(2),
                o1      = Signal(2),
                o2      = Signal(2),
                oe1     = Signal(2),
                oe2     = None,
                i1      = Signal(2),
                i2      = Signal(2),
                clk     = Signal(),
                i_async = Signal(2),
            )

    def test_differential_input_rejects_vector_signals(self):
        with self.assertRaisesRegex(ValueError, "single-bit"):
            DifferentialInput(Signal(2), Signal(2), Signal(2))

    def test_differential_output_rejects_vector_signals(self):
        with self.assertRaisesRegex(ValueError, "single-bit"):
            DifferentialOutput(Signal(2), Signal(2), Signal(2))

    def test_clk_output_rejects_string_input(self):
        with self.assertRaisesRegex(ValueError, "ClkOutput input"):
            ClkOutput("sys", Signal())


if __name__ == "__main__":
    unittest.main()
