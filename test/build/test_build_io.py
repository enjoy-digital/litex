import unittest

from migen import *
from migen.fhdl.specials import Tristate

from litex.build.altera.common import altera_special_overrides
from litex.build.colognechip.common import colognechip_special_overrides
from litex.build.efinix.common import EfinixTrionDDRTristateImpl
from litex.build.gowin.common import gowin_special_overrides, gw5a_special_overrides
from litex.build.io import (
    ClkInput,
    ClkOutput,
    DDRInput,
    DDROutput,
    DDRTristate,
    DifferentialInput,
    DifferentialOutput,
    InferredDDRTristate,
    InferredSDRIO,
    InferredSDRTristate,
    SDRInput,
    SDROutput,
    SDRTristate,
)
from litex.build.lattice.common import (
    lattice_NX_special_overrides,
    lattice_ecp5_trellis_special_overrides,
    lattice_ice40_special_overrides,
)
from litex.build.sim.common import sim_special_overrides
from litex.build.xilinx.common import (
    xilinx_s7_special_overrides,
    xilinx_special_overrides,
)
from litex.build.xilinx.platform import XilinxUSPlatform
from litex.gen.fhdl import verilog


def _merge_overrides(*overrides):
    merged = {}
    for override in overrides:
        merged.update(override)
    return merged


IO_OVERRIDE_MATRIX = {
    "altera"        : altera_special_overrides,
    "colognechip"  : colognechip_special_overrides,
    "gowin"        : gowin_special_overrides,
    "gw5a"         : _merge_overrides(gowin_special_overrides, gw5a_special_overrides),
    "lattice-ecp5" : lattice_ecp5_trellis_special_overrides,
    "lattice-ice40": lattice_ice40_special_overrides,
    "lattice-nx"   : lattice_NX_special_overrides,
    "sim"          : sim_special_overrides,
    "xilinx-s7"    : _merge_overrides(xilinx_special_overrides, xilinx_s7_special_overrides),
}


def _convert_special(special, ios, overrides):
    dut = Module()
    dut.specials += special
    return str(verilog.convert(dut, ios=ios, special_overrides=overrides))


def _io_primitive_cases():
    clk = Signal()

    i_p = Signal()
    i_n = Signal()
    o   = Signal()
    yield "diff-input", DifferentialInput(i_p, i_n, o), {i_p, i_n, o}

    i   = Signal()
    o_p = Signal()
    o_n = Signal()
    yield "diff-output", DifferentialOutput(i, o_p, o_n), {i, o_p, o_n}

    i = Signal(2)
    o = Signal(2)
    yield "sdr-input", SDRInput(i, o, clk), {i, o, clk}

    i = Signal(2)
    o = Signal(2)
    yield "sdr-output", SDROutput(i, o, clk), {i, o, clk}

    i = Signal(2)
    o1 = Signal(2)
    o2 = Signal(2)
    yield "ddr-input", DDRInput(i, o1, o2, clk), {i, o1, o2, clk}

    i1 = Signal(2)
    i2 = Signal(2)
    o = Signal(2)
    yield "ddr-output", DDROutput(i1, i2, o, clk), {i1, i2, o, clk}

    io = Signal(2)
    o = Signal(2)
    oe = Signal(2)
    i = Signal(2)
    yield "sdr-tristate", SDRTristate(io, o, oe, i, clk), {io, o, oe, i, clk}

    io = Signal(2)
    o1 = Signal(2)
    o2 = Signal(2)
    oe1 = Signal(2)
    i1 = Signal(2)
    i2 = Signal(2)
    i_async = Signal(2)
    yield "ddr-tristate", DDRTristate(io, o1, o2, oe1, i1=i1, i2=i2, clk=clk, i_async=i_async), {
        io, o1, o2, oe1, i1, i2, i_async, clk
    }


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

    def test_xilinx_s7_sdr_output_uses_single_edge_ff(self):
        i   = Signal(2)
        o   = Signal(2)
        clk = Signal()

        v = _convert_special(
            SDROutput(i, o, clk),
            {i, o, clk},
            _merge_overrides(xilinx_special_overrides, xilinx_s7_special_overrides),
        )

        self.assertEqual(v.count(" of FDCE Module."), 2)
        self.assertNotIn("ODDR", v)

    def test_xilinx_s7_ddr_output_still_uses_oddr(self):
        i1  = Signal(2)
        i2  = Signal(2)
        o   = Signal(2)
        clk = Signal()

        v = _convert_special(
            DDROutput(i1, i2, o, clk),
            {i1, i2, o, clk},
            _merge_overrides(xilinx_special_overrides, xilinx_s7_special_overrides),
        )

        self.assertEqual(v.count(" of ODDR Module."), 2)

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

    def test_gowin_inout_slices_are_normalized(self):
        for name, overrides in {
            "gowin": gowin_special_overrides,
            "gw5a" : _merge_overrides(gowin_special_overrides, gw5a_special_overrides),
        }.items():
            with self.subTest(name=name):
                dut  = Module()
                pads = Signal(16)
                o    = Signal(8)
                oe   = Signal()
                i    = Signal(8)

                dut.specials += Tristate(pads[0:8], o, oe, i)

                v = str(verilog.convert(
                    dut,
                    ios               = {pads, o, oe, i},
                    special_overrides = overrides,
                ))
                self.assertNotIn("[7:0][", v)
                self.assertIn(".IO  (pads[0])", v)
                self.assertIn(".IO  (pads[7])", v)

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

    def test_lattice_ice40_ddr_tristate_uses_physical_io_cells(self):
        io  = Signal(4)
        o1  = Signal(4)
        o2  = Signal(4)
        oe  = Signal(4)
        i1  = Signal(4)
        i2  = Signal(4)
        clk = Signal()

        v = _convert_special(
            DDRTristate(io, o1, o2, oe, i1=i1, i2=i2, clk=clk),
            {io, o1, o2, oe, i1, i2, clk},
            lattice_ice40_special_overrides,
        )

        self.assertEqual(v.count(" of SB_IO Module."), 4)
        self.assertEqual(v.count(".PIN_TYPE    (6'd48)"), 4)
        self.assertIn(".PACKAGE_PIN   (io[0])", v)
        self.assertIn(".PACKAGE_PIN   (io[3])", v)
        self.assertNotIn("inferredddrtristate", v)

    def test_lattice_ice40_ddr_tristate_preserves_i_async(self):
        io      = Signal(2)
        o1      = Signal(2)
        o2      = Signal(2)
        oe      = Signal(2)
        i1      = Signal(2)
        i2      = Signal(2)
        i_async = Signal(2)
        clk     = Signal()

        v = _convert_special(
            DDRTristate(io, o1, o2, oe, i1=i1, i2=i2, clk=clk, i_async=i_async),
            {io, o1, o2, oe, i1, i2, i_async, clk},
            lattice_ice40_special_overrides,
        )

        self.assertEqual(v.count(" of SB_IO Module."), 2)
        self.assertEqual(v.count(".PIN_TYPE    (6'd49)"), 2)
        self.assertEqual(v.count(" of SB_DFF Module."), 2)
        self.assertNotIn("inferredddrtristate", v)

    def test_lattice_ice40_ddr_tristate_rejects_ddr_output_enable(self):
        io  = Signal()
        o1  = Signal()
        o2  = Signal()
        oe1 = Signal()
        oe2 = Signal()
        clk = Signal()
        with self.assertRaisesRegex(ValueError, "DDR output enable"):
            _convert_special(
                DDRTristate(
                    io  = io,
                    o1  = o1,
                    o2  = o2,
                    oe1 = oe1,
                    oe2 = oe2,
                    clk = clk,
                ),
                {io, o1, o2, oe1, oe2, clk},
                lattice_ice40_special_overrides,
            )

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

    def test_io_primitive_override_matrix_converts(self):
        unsupported = {
            ("lattice-nx", "diff-input"),
            ("lattice-nx", "diff-output"),
            ("sim", "diff-input"),
            ("sim", "diff-output"),
        }
        for vendor, overrides in IO_OVERRIDE_MATRIX.items():
            for primitive, special, ios in _io_primitive_cases():
                with self.subTest(vendor=vendor, primitive=primitive):
                    if (vendor, primitive) in unsupported:
                        with self.assertRaises(NotImplementedError):
                            _convert_special(special, ios, overrides)
                    else:
                        v = _convert_special(special, ios, overrides)
                        self.assertIn("module top", v)

    def test_clock_io_is_explicitly_backend_specific(self):
        clk_i = Signal()
        clk_o = Signal()
        with self.assertRaises(NotImplementedError):
            _convert_special(ClkInput(clk_i, clk_o), {clk_i, clk_o}, {})
        with self.assertRaises(NotImplementedError):
            _convert_special(ClkOutput(clk_i, clk_o), {clk_i, clk_o}, {})


if __name__ == "__main__":
    unittest.main()
