#
# This file is part of LiteX.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import io
import unittest
from contextlib import redirect_stdout

from migen import *

from litex.soc.cores.clock import *
from litex.soc.cores.clock.gowin_gw1n import GW1NOSC, GW1NPLL
from litex.soc.cores.clock.gowin_gw5a import GW5APLL


class _FakeEfinixIfaceWriter:
    def __init__(self):
        self.blocks = []

    def get_block(self, name):
        for block in self.blocks:
            if block["name"] == name:
                return block
        raise ValueError("Unknown block: {}.".format(name))


class _FakeEfinixToolchain:
    def __init__(self):
        self.ifacewriter = _FakeEfinixIfaceWriter()
        self.excluded_ios = []


class _FakeEfinixPlatform:
    def __init__(self, family="Titanium"):
        self.family    = family
        self.device    = "T20"
        self.toolchain = _FakeEfinixToolchain()
        self.clks      = {}
        self.pll_used      = 0
        self.pll_available = 4

    def add_iface_io(self, name):
        return Signal(name=name)

    def get_pin_name(self, clkin):
        if clkin is None:
            raise ValueError("No pin signal provided.")
        return clkin.name_override or "clk"

    def get_pin_location(self, clkin):
        return []

    def get_free_pll_resource(self):
        resource = "PLL{}".format(self.pll_used)
        self.pll_used += 1
        return resource


class TestClock(unittest.TestCase):
    def assert_frequency_close(self, actual, expected, margin=1e-2):
        self.assertAlmostEqual(actual, expected, delta=expected*margin)

    def get_efinix_pll_block(self, pll):
        return pll.platform.toolchain.ifacewriter.get_block(pll.name)

    # Xilinx / Spartan 6
    def test_s6_pll(self):
        pll = S6PLL()
        pll.register_clkin(Signal(), 100e6)
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        pll.compute_config()

    def test_s6_dcm(self):
        dcm = S6DCM()
        dcm.register_clkin(Signal(), 100e6)
        for i in range(dcm.nclkouts_max):
            dcm.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        dcm.compute_config()

    # Xilinx / 7-Series
    def test_s7_pll(self):
        pll = S7PLL()
        pll.register_clkin(Signal(), 100e6)
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        pll.compute_config()

    def test_s7_mmcm(self):
        mmcm = S7MMCM()
        mmcm.register_clkin(Signal(), 100e6)
        for i in range(mmcm.nclkouts_max):
            mmcm.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        mmcm.compute_config()

    # Xilinx / Ultrascale
    def test_us_pll(self):
        pll = USPLL()
        pll.register_clkin(Signal(), 100e6)
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        pll.compute_config()

    def test_us_mmcm(self):
        mmcm = USMMCM()
        mmcm.register_clkin(Signal(), 100e6)
        for i in range(mmcm.nclkouts_max):
            mmcm.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        mmcm.compute_config()

    # Xilinx / Ultrascale Plus
    def test_us_ppll(self):
        pll = USPPLL()
        pll.register_clkin(Signal(), 100e6)
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        pll.compute_config()

    def test_us_pmmcm(self):
        mmcm = USPMMCM()
        mmcm.register_clkin(Signal(), 100e6)
        for i in range(mmcm.nclkouts_max):
            mmcm.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        mmcm.compute_config()

    # Intel / CycloneIV
    def test_cycloneiv_pll(self):
        pll = CycloneIVPLL()
        pll.register_clkin(Signal(), 50e6)
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 100e6)
        pll.compute_config()

    # Intel / CycloneV
    def test_cyclonev_pll(self):
        pll = CycloneVPLL()
        pll.register_clkin(Signal(), 50e6)
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 100e6)
        pll.compute_config()

    # Intel / Cyclone10
    def test_cyclone10_pll(self):
        pll = Cyclone10LPPLL()
        pll.register_clkin(Signal(), 50e6)
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 100e6)
        pll.compute_config()

    # Intel / Max10
    def test_max10_pll(self):
        pll = Max10PLL()
        pll.register_clkin(Signal(), 50e6)
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 100e6)
        pll.compute_config()

    # Lattice / iCE40
    def test_ice40_pll(self):
        pll = iCE40PLL()
        pll.register_clkin(Signal(), 100e6)
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        pll.compute_config()

    def test_ice40_pll_rejects_out_of_range_frequencies(self):
        pll = iCE40PLL()
        with self.assertRaisesRegex(ValueError, "Input clock frequency"):
            pll.register_clkin(Signal(), 1e9)

        pll.register_clkin(Signal(), 100e6)
        with self.assertRaisesRegex(ValueError, "Output clock frequency"):
            pll.create_clkout(ClockDomain("clkout"), 1e9)

    def test_xilinx_plls_reject_out_of_range_clkin(self):
        test_cases = [
            (S6PLL,   600e6),
            (S7PLL,     1e9),
            (S7MMCM,  1.2e9),
            (USPLL,    50e6),
        ]
        for pll_cls, clkin_freq in test_cases:
            with self.subTest(pll=pll_cls.__name__):
                pll = pll_cls()
                with self.assertRaisesRegex(ValueError, "Input clock frequency"):
                    pll.register_clkin(Signal(), clkin_freq)

    def test_intel_plls_reject_out_of_range_frequencies(self):
        pll = CycloneVPLL()
        with self.assertRaisesRegex(ValueError, "Input clock frequency"):
            pll.register_clkin(Signal(), 1e9)

        pll.register_clkin(Signal(), 50e6)
        with self.assertRaisesRegex(ValueError, "Output clock frequency"):
            pll.create_clkout(ClockDomain("clkout"), 600e6)

    def test_agilex_pll_rejects_out_of_range_clkout(self):
        pll = Agilex5PLL(platform=None)
        pll.register_clkin(Signal(), 100e6)
        with self.assertRaisesRegex(ValueError, "Output clock frequency"):
            pll.create_clkout(ClockDomain("clkout"), 1e9)

    def test_lattice_plls_reject_out_of_range_frequencies(self):
        test_cases = [
            (ECP5PLL, 100e6, 1e9, 1e9),
            (NXPLL,   100e6, 1e9, 1e9),
        ]
        for pll_cls, valid_clkin_freq, invalid_clkin_freq, invalid_clkout_freq in test_cases:
            with self.subTest(pll=pll_cls.__name__):
                pll = pll_cls()
                with self.assertRaisesRegex(ValueError, "Input clock frequency"):
                    pll.register_clkin(Signal(), invalid_clkin_freq)

                pll.register_clkin(Signal(), valid_clkin_freq)
                with self.assertRaisesRegex(ValueError, "Output clock frequency"):
                    pll.create_clkout(ClockDomain("clkout"), invalid_clkout_freq)

    def test_ice40_pll_finalize_accepts_max_input_frequency(self):
        pll = iCE40PLL()
        pll.register_clkin(Signal(), 133e6)
        pll.create_clkout(ClockDomain("clkout"), 133e6)
        pll.get_fragment()

    # Lattice / ECP5
    def test_ecp5_pll(self):
        pll = ECP5PLL()
        pll.register_clkin(Signal(), 100e6)
        for i in range(pll.nclkouts_max-1):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 200e6, uses_dpa=(i != 0))
        pll.expose_dpa()
        pll.compute_config()

        # Test corner cases that have historically had trouble:
        pll = ECP5PLL()
        pll.register_clkin(Signal(), 100e6)
        pll.create_clkout(ClockDomain("clkout1"), 350e6)
        pll.create_clkout(ClockDomain("clkout2"), 350e6)
        pll.create_clkout(ClockDomain("clkout3"), 175e6)
        pll.create_clkout(ClockDomain("clkout4"), 175e6)
        pll.compute_config()

    def test_ecp5_dynamic_delay(self):
        delay = ECP5DynamicDelay(i=Signal(), o=Signal(), taps=Signal(7))
        delay = ECP5DynamicDelay()

    # Lattice / NX
    def test_nxpll(self):
        pll = NXPLL()
        pll.register_clkin(Signal(), 100e6)
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 200e6)
        pll.compute_config()

    def test_nxosca_hfsdc_clk_can_be_used_without_hf_clk(self):
        osc = NXOSCA()
        osc.create_hfsdc_clk(ClockDomain("hfsdc"), 45e6)
        osc.do_finalize()

        self.assertEqual(osc.params["p_HF_SED_SEC_DIV"], "9")
        self.assertIn("o_HFSDCOUT", osc.params)

    def test_nxosca_hf_and_hfsdc_clks_use_independent_divisors(self):
        osc = NXOSCA()
        osc.create_hf_clk(ClockDomain("hf"), 90e6)
        osc.create_hfsdc_clk(ClockDomain("hfsdc"), 45e6)
        osc.do_finalize()

        self.assertEqual(osc.params["p_HF_CLK_DIV"],     "4")
        self.assertEqual(osc.params["p_HF_SED_SEC_DIV"], "9")

    def test_nxosca_rejects_out_of_range_hf_clk(self):
        osc = NXOSCA()
        with self.assertRaisesRegex(ValueError, "HF clock frequency"):
            osc.create_hf_clk(ClockDomain("hf"), 1e6)

    def test_nxpll_finalize_is_quiet(self):
        pll = NXPLL()
        pll.register_clkin(Signal(), 100e6)
        pll.create_clkout(ClockDomain("clkout"), 200e6)
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            pll.get_fragment()

        self.assertEqual(stdout.getvalue(), "")

    def test_gatemate_pll_rejects_invalid_output_config(self):
        pll = GateMatePLL()
        pll.register_clkin(Signal(), 50e6)
        with self.assertRaisesRegex(ValueError, "Output clock frequency"):
            pll.create_clkout(ClockDomain("clkout"), 300e6)
        with self.assertRaisesRegex(ValueError, "Output clock phase"):
            pll.create_clkout(ClockDomain("clkout"), 100e6, phase=45)

    def test_ice40_pll_rejects_invalid_primitive(self):
        with self.assertRaisesRegex(ValueError, "Unsupported iCE40 PLL primitive"):
            iCE40PLL(primitive="SB_PLL40_BAD")

    def test_xilinx_dps_csr_requires_sys_domain(self):
        pll = S7PLL()
        with self.assertRaisesRegex(ValueError, "sys clock domain"):
            pll.expose_dps(clk_domain="idelay", with_csr=True)

        pll.expose_dps(clk_domain="idelay", with_csr=False)

    def test_gatemate_pll_rejects_invalid_constructor_args(self):
        test_cases = [
            ("perf_mode",  lambda: GateMatePLL(perf_mode="turbo"), "performance mode"),
            ("low_jitter", lambda: GateMatePLL(low_jitter=2),      "low_jitter"),
            ("lock_req",   lambda: GateMatePLL(lock_req=2),        "lock_req"),
        ]
        for name, pll_factory, message in test_cases:
            with self.subTest(argument=name):
                with self.assertRaisesRegex(ValueError, message):
                    pll_factory()

    def test_plls_reject_non_positive_frequencies(self):
        test_cases = [
            ("S7PLL",       lambda: S7PLL(),                              100e6),
            ("CycloneVPLL", lambda: CycloneVPLL(),                         50e6),
            ("Agilex5PLL",  lambda: Agilex5PLL(platform=None),            100e6),
            ("ECP5PLL",     lambda: ECP5PLL(),                            100e6),
            ("iCE40PLL",    lambda: iCE40PLL(),                            12e6),
            ("NXPLL",       lambda: NXPLL(),                              100e6),
            ("GateMatePLL", lambda: GateMatePLL(),                         50e6),
            ("GW1NPLL",     lambda: GW1NPLL("GW1N-9", "GW1N-9C"),          50e6),
            ("GW5APLL",     lambda: GW5APLL("GW5A-25", "GW5A-25"),         50e6),
        ]
        for name, pll_factory, clkin_freq in test_cases:
            with self.subTest(pll=name, clock="clkin"):
                pll = pll_factory()
                with self.assertRaisesRegex(ValueError, "Input clock frequency"):
                    pll.register_clkin(Signal(name="clk"), 0)

            with self.subTest(pll=name, clock="clkout"):
                pll = pll_factory()
                pll.register_clkin(Signal(name="clk"), clkin_freq)
                with self.assertRaisesRegex(ValueError, "Output clock frequency"):
                    pll.create_clkout(ClockDomain("clkout"), 0)

    def test_gw1n_osc_rejects_non_positive_frequency(self):
        with self.assertRaisesRegex(ValueError, "Oscillator frequency"):
            GW1NOSC("GW1N-4", 0)

    def test_gw1n_osc_prefers_closest_frequency(self):
        osc = GW1NOSC("GW1N-9", 110e6, margin=0.30)

        self.assertEqual(osc.config["div"], 2)
        self.assert_frequency_close(osc.config["freq"], 125e6, margin=1e-9)

    def test_clocking_rejects_negative_margins(self):
        test_cases = [
            ("S7PLL clkout", lambda: S7PLL().create_clkout(ClockDomain("clkout"), 100e6, margin=-1e-2)),
            ("GW1NOSC",      lambda: GW1NOSC("GW1N-9", 100e6, margin=-1e-2)),
            ("GW1NPLL VCO",  lambda: GW1NPLL("GW1N-9", "GW1N-9C", vco_margin=-1e-2)),
            ("NXOSCA HF",    lambda: NXOSCA().create_hf_clk(ClockDomain("hf"), 45e6, margin=-1e-2)),
            ("Efinix",       lambda: TITANIUMPLL(_FakeEfinixPlatform()).create_clkout(None, 100e6, margin=-1e-2)),
        ]
        for name, clocking_factory in test_cases:
            with self.subTest(clocking=name):
                with self.assertRaisesRegex(ValueError, "margin"):
                    clocking_factory()

    def test_efinix_pll_accepts_dyn_phase_pads(self):
        pads = {
            "shift_ena": Signal(),
            "shift":     Signal(),
            "shift_sel": Signal(2),
        }
        pll   = TITANIUMPLL(_FakeEfinixPlatform(), dyn_phase_shift_pads=pads)
        block = self.get_efinix_pll_block(pll)

        self.assertIs(block["shift_ena"], pads["shift_ena"])
        self.assertIs(block["shift"],     pads["shift"])
        self.assertIs(block["shift_sel"], pads["shift_sel"])

    def test_efinix_pll_rejects_incomplete_dyn_phase_pads(self):
        with self.assertRaisesRegex(ValueError, "dyn_phase_shift_pads"):
            TITANIUMPLL(_FakeEfinixPlatform(), dyn_phase_shift_pads={"shift_ena": Signal()})

    def test_efinix_pll_rejects_explicit_clkout_on_trion(self):
        pll = TRIONPLL(_FakeEfinixPlatform(family="Trion"))
        with self.assertRaisesRegex(ValueError, "not supported for Trion"):
            pll.create_clkout(None, 100e6, nclkout=0)

    def test_efinix_pll_rejects_invalid_clkout_index(self):
        pll = TITANIUMPLL(_FakeEfinixPlatform())
        with self.assertRaisesRegex(ValueError, "nclkout must be >= 0"):
            pll.create_clkout(None, 100e6, nclkout=-1)
        with self.assertRaisesRegex(ValueError, "nclkout must be less than"):
            pll.create_clkout(None, 100e6, nclkout=pll.nclkouts_max)

    def test_efinix_pll_rejects_used_clkout(self):
        pll = TITANIUMPLL(_FakeEfinixPlatform())
        pll.create_clkout(None, 100e6, nclkout=0)
        with self.assertRaisesRegex(ValueError, "already used"):
            pll.create_clkout(None, 100e6, nclkout=0)

    def test_efinix_pll_rejects_missing_free_clkout(self):
        pll = TITANIUMPLL(_FakeEfinixPlatform())
        for _ in range(pll.nclkouts_max):
            pll.create_clkout(None, 100e6)
        with self.assertRaisesRegex(ValueError, "No free clock output"):
            pll.create_clkout(None, 100e6)

    def test_efinix_pll_rejects_duplicate_feedback_clkout(self):
        pll = TITANIUMPLL(_FakeEfinixPlatform())
        pll.create_clkout(None, 100e6, is_feedback=True, nclkout=0)
        with self.assertRaisesRegex(ValueError, "Feedback clock output"):
            pll.create_clkout(None, 100e6, is_feedback=True, nclkout=1)

    def test_efinix_pll_registers_name_only_internal_clkin(self):
        pll = TITANIUMPLL(_FakeEfinixPlatform())
        pll.register_clkin(None, 50e6, name="core_clk")
        block = self.get_efinix_pll_block(pll)

        self.assertEqual(block["input_clock_name"], "core_clk")
        self.assertEqual(block["input_signal"], "core_clk")
        self.assertEqual(block["input_clock"], "INTERNAL")

    def test_efinix_pll_rejects_missing_internal_clkin_name(self):
        pll = TITANIUMPLL(_FakeEfinixPlatform())
        with self.assertRaisesRegex(ValueError, "No clkin name"):
            pll.register_clkin(None, 50e6)

    def test_efinix_pll_remaps_sparse_feedback_clkout(self):
        pll   = TRIONPLL(_FakeEfinixPlatform())
        block = self.get_efinix_pll_block(pll)
        block["input_freq"] = 50e6

        pll.create_clkout(None, 100e6, nclkout=2, is_feedback=True)
        pll.compute_config()

        self.assertEqual(block["feedback"], 0)
        self.assertEqual(len(block["clk_out"]), 1)
        self.assertIn("CLKOUT0_DIV", block)

    def test_efinix_pll_rejects_unconfigured_feedback_clkout(self):
        pll   = TRIONPLL(_FakeEfinixPlatform())
        block = self.get_efinix_pll_block(pll)
        block["input_freq"] = 50e6
        block["feedback"]   = 2

        pll.create_clkout(None, 100e6, nclkout=0)
        with self.assertRaisesRegex(ValueError, "Feedback clock output"):
            pll.compute_config()

    def test_efinix_pll_rejects_unsupported_phase(self):
        pll   = TRIONPLL(_FakeEfinixPlatform())
        block = self.get_efinix_pll_block(pll)
        block["input_freq"] = 50e6

        pll.create_clkout(None, 100e6, phase=30, is_feedback=True)
        with self.assertRaisesRegex(ValueError, "PLL clock phase"):
            pll.compute_config()

    def test_efinix_pll_tolerates_subhz_float_noise(self):
        pll   = TRIONPLL(_FakeEfinixPlatform())
        block = self.get_efinix_pll_block(pll)
        block["input_freq"] = 50e6

        pll.create_clkout(None, 100e6 + 1e-7, is_feedback=True)
        pll.compute_config()

        self.assertIn("CLKOUT0_DIV", block)

    def test_plls_reject_missing_clkout(self):
        test_cases = [
            ("S7PLL",       lambda: S7PLL(),                              100e6),
            ("CycloneVPLL", lambda: CycloneVPLL(),                         50e6),
            ("Agilex5PLL",  lambda: Agilex5PLL(platform=None),            100e6),
            ("ECP5PLL",     lambda: ECP5PLL(),                            100e6),
            ("iCE40PLL",    lambda: iCE40PLL(),                            12e6),
            ("NXPLL",       lambda: NXPLL(),                              100e6),
            ("GW1NPLL",     lambda: GW1NPLL("GW1N-9", "GW1N-9C"),          50e6),
            ("GW5APLL",     lambda: GW5APLL("GW5A-25", "GW5A-25"),         50e6),
        ]
        for name, pll_factory, clkin_freq in test_cases:
            with self.subTest(pll=name):
                pll = pll_factory()
                pll.register_clkin(Signal(name="clk"), clkin_freq)
                with self.assertRaisesRegex(ValueError, "At least one output clock"):
                    pll.compute_config()

    def test_pll_rejects_missing_clkin(self):
        pll = S7PLL()
        pll.create_clkout(ClockDomain("clkout"), 100e6)
        with self.assertRaisesRegex(ValueError, "Input clock"):
            pll.compute_config()

    def test_pll_rejects_too_many_clkouts(self):
        pll = S7PLL()
        for i in range(pll.nclkouts_max):
            pll.create_clkout(ClockDomain("clkout{}".format(i)), 100e6)
        with self.assertRaisesRegex(ValueError, "Cannot add more"):
            pll.create_clkout(ClockDomain("clkout_extra"), 100e6)

    def test_plls_reject_duplicate_clkout_domain(self):
        test_cases = [
            ("S6PLL",        lambda: S6PLL(),                              100e6, 200e6),
            ("S6DCM",        lambda: S6DCM(),                              100e6, 200e6),
            ("S7PLL",        lambda: S7PLL(),                              100e6, 200e6),
            ("S7MMCM",       lambda: S7MMCM(),                             100e6, 200e6),
            ("USPLL",        lambda: USPLL(),                              100e6, 200e6),
            ("USMMCM",       lambda: USMMCM(),                             100e6, 200e6),
            ("USPPLL",       lambda: USPPLL(),                             100e6, 200e6),
            ("USPMMCM",      lambda: USPMMCM(),                            100e6, 200e6),
            ("CycloneIVPLL", lambda: CycloneIVPLL(),                        50e6, 100e6),
            ("CycloneVPLL",  lambda: CycloneVPLL(),                         50e6, 100e6),
            ("Cyclone10PLL", lambda: Cyclone10LPPLL(),                      50e6, 100e6),
            ("Max10PLL",     lambda: Max10PLL(),                            50e6, 100e6),
            ("Agilex5PLL",   lambda: Agilex5PLL(platform=None),            100e6, 100e6),
            ("ECP5PLL",      lambda: ECP5PLL(),                            100e6, 200e6),
            ("iCE40PLL",     lambda: iCE40PLL(),                            12e6,  48e6),
            ("NXPLL",        lambda: NXPLL(),                              100e6, 200e6),
            ("GateMatePLL",  lambda: GateMatePLL(),                         50e6, 100e6),
            ("GW1NPLL",      lambda: GW1NPLL("GW1N-9", "GW1N-9C"),          50e6, 100e6),
            ("GW5APLL",      lambda: GW5APLL("GW5A-25", "GW5A-25"),         50e6, 100e6),
        ]
        for name, pll_factory, clkin_freq, clkout_freq in test_cases:
            with self.subTest(pll=name):
                pll = pll_factory()
                cd  = ClockDomain("clkout")
                pll.register_clkin(Signal(), clkin_freq)
                pll.create_clkout(cd, clkout_freq)
                with self.assertRaisesRegex(ValueError, "already driven"):
                    pll.create_clkout(cd, clkout_freq)

    def test_pll_rejects_duplicate_clkout_domain_name(self):
        pll = S7PLL()
        pll.register_clkin(Signal(), 100e6)
        pll.create_clkout(ClockDomain("clkout"), 100e6)
        with self.assertRaisesRegex(ValueError, "already driven"):
            pll.create_clkout(ClockDomain("clkout"), 200e6)

    def test_efinix_pll_rejects_duplicate_clkout_domain(self):
        pll = TITANIUMPLL(_FakeEfinixPlatform())
        cd  = ClockDomain("clkout")

        pll.create_clkout(cd, 100e6)
        with self.assertRaisesRegex(ValueError, "already driven"):
            pll.create_clkout(cd, 100e6)

    def test_nxosca_rejects_duplicate_clkout_domain(self):
        osc = NXOSCA()
        cd  = ClockDomain("clkout")

        osc.create_hf_clk(cd, 45e6)
        with self.assertRaisesRegex(ValueError, "already driven"):
            osc.create_hfsdc_clk(cd, 45e6)

    def test_gw5a_pll_rejects_unreachable_high_clkout(self):
        pll = GW5APLL("GW5A-25", "GW5A-25")
        pll.register_clkin(Signal(), 50e6)
        pll.create_clkout(ClockDomain("clkout"), 10e9)
        with self.assertRaisesRegex(ValueError, r"No PLL config found.*ClkIn=50.00MHz.*ClkOut0=10000.00MHz"):
            pll.compute_config()

    def test_gw1n_pll_rejects_multiple_nonzero_phases(self):
        pll = GW1NPLL("GW1N-9", "GW1N-9C")
        pll.register_clkin(Signal(), 50e6)
        pll.create_clkout(ClockDomain("clkout0"), 100e6, phase=90)
        pll.create_clkout(ClockDomain("clkout1"), 100e6, phase=180)
        with self.assertRaisesRegex(ValueError, "only one non-zero phase"):
            pll.compute_config()

    def test_pll_configs_prefer_closest_frequency(self):
        test_cases = [
            (S7PLL,    100e6, 70e6,     0.20, "clkout0_freq"),
            (USPMMCM,  100e6, 70e6,     0.25, "clkout0_freq"),
            (ECP5PLL,  100e6, 10e6,     0.20, "clko0_freq"),
            (NXPLL,    100e6, 10e6,     0.20, "clko0_freq"),
            (iCE40PLL,  12e6, 16.125e6, 0.20, "clkout_freq"),
        ]
        for pll_cls, clkin_freq, clkout_freq, margin, freq_key in test_cases:
            with self.subTest(pll=pll_cls.__name__):
                pll = pll_cls()
                pll.register_clkin(Signal(), clkin_freq)
                pll.create_clkout(ClockDomain("clkout"), clkout_freq, margin=margin)
                config = pll.compute_config()

                self.assert_frequency_close(config[freq_key], clkout_freq, margin=1e-9)

    def test_intel_pll_config_score_balances_outputs(self):
        pll = CycloneVPLL()
        pll.register_clkin(Signal(), 50e6)
        pll.create_clkout(ClockDomain("clkout0"), 20e6, margin=.05)
        pll.create_clkout(ClockDomain("clkout1"), 31e6, margin=.05)
        config = pll.compute_config()

        self.assert_frequency_close(config["clk0_freq"], 20e6, margin=1e-9)
        self.assert_frequency_close(config["clk1_freq"], 31e6, margin=1e-9)

    def test_pll_configs_match_requested_frequencies(self):
        test_cases = [
            (S7PLL,        100e6, 200e6, "clkout0_freq", 0),
            (S7MMCM,       100e6, 125e6, "clkout0_freq", 90),
            (CycloneVPLL,   50e6, 100e6, "clk0_freq",    45),
            (ECP5PLL,      100e6, 200e6, "clko0_freq",   90),
            (iCE40PLL,      12e6,  48e6, "clkout_freq",   0),
        ]
        for pll_cls, clkin_freq, clkout_freq, freq_key, phase in test_cases:
            with self.subTest(pll=pll_cls.__name__):
                pll = pll_cls()
                pll.register_clkin(Signal(), clkin_freq)
                if phase:
                    pll.create_clkout(ClockDomain("clkout"), clkout_freq, phase=phase)
                else:
                    pll.create_clkout(ClockDomain("clkout"), clkout_freq)
                config = pll.compute_config()

                self.assert_frequency_close(config[freq_key], clkout_freq)
                if phase:
                    self.assertEqual(config[freq_key.replace("freq", "phase")], phase)

    def test_agilex_pll_uses_relative_frequency_margin(self):
        pll = Agilex5PLL(platform=None)
        pll.register_clkin(Signal(), 100e6)
        pll.create_clkout(ClockDomain("clkout"), 123.4e6, margin=1e-2)
        config = pll.compute_config()

        self.assert_frequency_close(config["clk0_freq"], 123.4e6)

    def test_common_pll_finalize_smoke(self):
        test_cases = [
            (S6PLL,        100e6, 200e6),
            (S6DCM,        100e6, 200e6),
            (S7PLL,        100e6, 200e6),
            (S7MMCM,       100e6, 200e6),
            (USPLL,        100e6, 200e6),
            (USMMCM,       100e6, 200e6),
            (USPPLL,       100e6, 200e6),
            (USPMMCM,      100e6, 200e6),
            (CycloneIVPLL,  50e6, 100e6),
            (CycloneVPLL,   50e6, 100e6),
            (Cyclone10LPPLL, 50e6, 100e6),
            (Max10PLL,      50e6, 100e6),
            (ECP5PLL,      100e6, 200e6),
            (iCE40PLL,      12e6,  48e6),
            (NXPLL,        100e6, 200e6),
            (GateMatePLL,   50e6, 100e6),
            (lambda: GW1NPLL("GW1N-9", "GW1N-9C"), 50e6, 100e6),
            (lambda: GW5APLL("GW5A-25", "GW5A-25"), 50e6, 100e6),
        ]
        for pll_cls, clkin_freq, clkout_freq in test_cases:
            pll = pll_cls()
            with self.subTest(pll=pll.__class__.__name__):
                pll.register_clkin(Signal(), clkin_freq)
                pll.create_clkout(ClockDomain("clkout"), clkout_freq)
                pll.get_fragment()
