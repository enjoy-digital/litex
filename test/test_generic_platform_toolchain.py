#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import tempfile
import unittest

from migen import ClockDomain, Module, Signal

from litex.build.generic_platform import (
    ConstraintError,
    GenericPlatform,
    Inverted,
    IOStandard,
    Misc,
    Pins,
    PlatformInfo,
    Subsignal,
)
from litex.build.generic_toolchain import GenericToolchain


_IO = [
    ("clk",      0, Pins("J:0"), IOStandard("LVCMOS33")),
    ("user_led", 0, Pins("A1"),  IOStandard("LVCMOS33"), Misc("PULLUP"), PlatformInfo({"role": "led"})),
    ("user_led", 1, Pins("A2")),
    ("serial",   0,
        Subsignal("tx", Pins("J:1")),
        Subsignal("rx", Pins("J:2"), Inverted()),
        IOStandard("LVCMOS33"),
    ),
    ("wide",     0, Pins(3)),
]

_CONNECTORS = [
    ("J", "P1 P2 P3"),
    ("K", {"A": "J:0"}),
]


class _DummyToolchain(GenericToolchain):
    def __init__(self):
        GenericToolchain.__init__(self)
        self.finalize_calls = 0
        self.project_calls  = 0
        self.script_calls   = 0
        self.run_calls      = []

    def finalize(self):
        self.finalize_calls += 1

    def build_io_constraints(self):
        return ("io.pcf", "PCF")

    def build_timing_constraints(self, vns):
        return ("timing.sdc", "SDC")

    def build_project(self):
        self.project_calls += 1

    def build_script(self):
        self.script_calls += 1
        return "build.sh"

    def run_script(self, script):
        self.run_calls.append(script)


def _make_platform(io=None, connectors=None):
    return GenericPlatform(
        device     = "unit-device",
        io         = _IO if io is None else io,
        connectors = _CONNECTORS if connectors is None else connectors,
        name       = "unit_platform",
    )


class TestConstraintManager(unittest.TestCase):
    def test_request_signal_resource_with_platform_info(self):
        platform = _make_platform()

        led = platform.request("user_led", 0)

        self.assertEqual(len(led), 1)
        self.assertEqual(led.platform_info, {"role": "led"})
        self.assertIs(platform.lookup_request("user_led", 0), led)

    def test_request_record_resource_tracks_subsignal_inversion(self):
        platform = _make_platform()

        serial = platform.request("serial")

        self.assertTrue(serial.rx.inverted)
        self.assertIs(platform.lookup_request("serial:tx"), serial.tx)
        self.assertIs(platform.lookup_request("serial:rx"), serial.rx)

    def test_reserve_false_does_not_consume_resource(self):
        platform = _make_platform()

        loose_led = platform.request("user_led", 0, reserve=False)
        reserved  = platform.request("user_led", 0)

        self.assertIsNot(loose_led, reserved)
        self.assertIs(platform.lookup_request("user_led", 0), reserved)

    def test_missing_request_loose_returns_none(self):
        platform = _make_platform()

        self.assertIsNone(platform.request("missing", loose=True))
        with self.assertRaises(ConstraintError):
            platform.request("missing")

    def test_lookup_request_loose_handles_missing_resource_and_subsignal(self):
        platform = _make_platform()

        self.assertIsNone(platform.lookup_request("user_led", 0, loose=True))
        with self.assertRaises(ConstraintError):
            platform.lookup_request("user_led", 0)

        platform.request("serial")
        self.assertIsNone(platform.lookup_request("serial:cts", loose=True))
        with self.assertRaisesRegex(ConstraintError, "serial:None:cts"):
            platform.lookup_request("serial:cts")

    def test_request_all_and_remaining_collect_resources(self):
        platform_all = _make_platform()
        platform_rem = _make_platform()

        all_leds = platform_all.request_all("user_led")
        rest     = platform_rem.request_remaining("user_led")

        self.assertEqual(len(all_leds), 2)
        self.assertEqual(len(rest),     2)

    def test_request_all_stops_at_first_numbering_gap(self):
        platform = _make_platform(io=[
            ("lane", 0, Pins("A1")),
            ("lane", 2, Pins("A2")),
        ])

        lanes = platform.request_all("lane")

        self.assertEqual(len(lanes), 1)
        self.assertIsNotNone(platform.request("lane", 2))

    def test_request_remaining_skips_reserved_resources(self):
        platform = _make_platform()

        platform.request("user_led", 0)
        rest = platform.request_remaining("user_led")

        self.assertEqual(len(rest), 1)
        self.assertIsNotNone(platform.lookup_request("user_led", 1))

    def test_extension_prepend_overrides_matching_resource(self):
        platform = _make_platform()

        platform.add_extension([("user_led", 0, Pins("Z9"))], prepend=True)
        led = platform.request("user_led", 0)
        constraints = platform.constraint_manager.get_sig_constraints()

        self.assertIs(constraints[0][0], led)
        self.assertEqual(constraints[0][1], ["Z9"])

    def test_extension_append_keeps_existing_resource_priority(self):
        platform = _make_platform()

        platform.add_extension([("user_led", 0, Pins("Z9"))], prepend=False)
        led = platform.request("user_led", 0)
        constraints = platform.constraint_manager.get_sig_constraints()

        self.assertIs(constraints[0][0], led)
        self.assertEqual(constraints[0][1], ["A1"])

    def test_connector_resolution_supports_string_dict_and_recursion(self):
        platform = _make_platform(io=[("debug", 0, Pins("K:A"))])

        debug = platform.request("debug")
        constraints = platform.constraint_manager.get_sig_constraints()

        self.assertIs(constraints[0][0], debug)
        self.assertEqual(constraints[0][1], ["P1"])

    def test_duplicate_connectors_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Connector specified more than once"):
            _make_platform(connectors=[("J", "P1"), ("J", "P2")])

    def test_connector_resolution_reports_missing_or_malformed_connectors(self):
        platform = _make_platform(io=[("debug", 0, Pins("M:0"))])
        platform.request("debug")
        with self.assertRaisesRegex(AssertionError, "No connector named 'M'"):
            platform.constraint_manager.get_sig_constraints()

        platform = _make_platform(io=[("debug", 0, Pins("J:5"))])
        platform.request("debug")
        with self.assertRaisesRegex(AssertionError, "maximum is 2"):
            platform.constraint_manager.get_sig_constraints()

        platform = _make_platform(io=[("debug", 0, Pins("K:B"))])
        platform.request("debug")
        with self.assertRaisesRegex(AssertionError, "There is no pin 'B'"):
            platform.constraint_manager.get_sig_constraints()

        platform = _make_platform(io=[("debug", 0, Pins("J:0:1"))])
        platform.request("debug")
        with self.assertRaisesRegex(ValueError, '"J:0:1"'):
            platform.constraint_manager.get_sig_constraints()

    def test_unsupported_connector_pin_list_type_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported pin list type"):
            _make_platform(connectors=[("J", ["P1"])])

    def test_resolved_sig_constraints_include_subsignals_and_top_constraints(self):
        platform = _make_platform()
        serial   = platform.request("serial")
        constraints = platform.constraint_manager.get_sig_constraints()
        by_name = {resource[2]: (sig, pins, others) for sig, pins, others, resource in constraints}

        self.assertIs(by_name["tx"][0], serial.tx)
        self.assertEqual(by_name["tx"][1], ["P2"])
        self.assertTrue(any(isinstance(c, IOStandard) for c in by_name["tx"][2]))
        self.assertIs(by_name["rx"][0], serial.rx)
        self.assertEqual(by_name["rx"][1], ["P3"])
        self.assertTrue(any(isinstance(c, Inverted) for c in by_name["rx"][2]))

    def test_top_level_inversion_and_no_connect_connector_pin_are_preserved(self):
        platform = _make_platform(
            io         = [("button", 0, Pins("J:1"), Inverted())],
            connectors = [("J", "P1 None P3")],
        )

        button = platform.request("button")
        constraints = platform.constraint_manager.get_sig_constraints()

        self.assertTrue(button.inverted)
        self.assertEqual(constraints[0][1], [None])

    def test_io_signals_include_flattened_record_fields(self):
        platform = _make_platform()

        led    = platform.request("user_led", 0)
        serial = platform.request("serial")
        io_signals = platform.constraint_manager.get_io_signals()

        self.assertIn(led, io_signals)
        self.assertIn(serial.tx, io_signals)
        self.assertIn(serial.rx, io_signals)

    def test_platform_command_resolution_uses_verilog_namespace_names(self):
        platform = _make_platform()
        led      = platform.request("user_led", 0)
        platform.add_platform_command("set_property MARK_DEBUG true {led}", led=led)

        class _VNS:
            def get_name(self, sig):
                return "resolved_led"

        _, commands = platform.resolve_signals(_VNS())

        self.assertEqual(commands, ["set_property MARK_DEBUG true resolved_led"])

    def test_platform_command_resolution_accepts_multiple_signals(self):
        platform = _make_platform()
        led0     = platform.request("user_led", 0)
        led1     = platform.request("user_led", 1)
        platform.add_platform_command("connect {src} {dst}", src=led0, dst=led1)

        class _VNS:
            def get_name(self, sig):
                return {
                    led0: "led0",
                    led1: "led1",
                }[sig]

        _, commands = platform.resolve_signals(_VNS())

        self.assertEqual(commands, ["connect led0 led1"])


class TestGenericPlatform(unittest.TestCase):
    def test_add_source_deduplicates_and_infers_language(self):
        platform = _make_platform()

        with tempfile.TemporaryDirectory() as tmp_dir:
            source = os.path.join(tmp_dir, "rtl.v")
            open(source, "w").close()

            platform.add_source(source)
            platform.add_source(source)

        self.assertEqual(len(platform.sources), 1)
        self.assertEqual(platform.sources[0][1], "verilog")
        self.assertEqual(platform.sources[0][2], "work")

    def test_add_source_can_mark_copy_and_custom_library(self):
        platform = _make_platform()

        with tempfile.TemporaryDirectory() as tmp_dir:
            source = os.path.join(tmp_dir, "rtl.sv")
            open(source, "w").close()
            platform.add_source(source, library="lib", copy=True)

        self.assertEqual(platform.sources[0][1], "systemverilog")
        self.assertEqual(platform.sources[0][2], "lib")
        self.assertEqual(platform.sources[0][3], True)

    def test_add_source_dir_filters_unknown_languages(self):
        platform = _make_platform()

        with tempfile.TemporaryDirectory() as tmp_dir:
            open(os.path.join(tmp_dir, "a.v"),   "w").close()
            open(os.path.join(tmp_dir, "b.txt"), "w").close()
            sub_dir = os.path.join(tmp_dir, "sub")
            os.makedirs(sub_dir)
            open(os.path.join(sub_dir, "c.vhd"), "w").close()

            platform.add_source_dir(tmp_dir)

        languages = [source[1] for source in platform.sources]
        self.assertCountEqual(languages, ["vhdl", "verilog"])

    def test_add_source_dir_can_be_non_recursive(self):
        platform = _make_platform()

        with tempfile.TemporaryDirectory() as tmp_dir:
            open(os.path.join(tmp_dir, "top.v"), "w").close()
            sub_dir = os.path.join(tmp_dir, "sub")
            os.makedirs(sub_dir)
            open(os.path.join(sub_dir, "sub.v"), "w").close()

            platform.add_source_dir(tmp_dir, recursive=False)

        self.assertEqual(len(platform.sources), 1)
        self.assertTrue(platform.sources[0][0].endswith("top.v"))

    def test_add_verilog_include_path_is_absolute(self):
        platform = _make_platform()

        platform.add_verilog_include_path("rtl/include")

        self.assertEqual(platform.verilog_include_paths, [os.path.abspath("rtl/include")])

    def test_finalize_adds_default_clock_and_rejects_second_finalize(self):
        platform = _make_platform()
        platform.default_clk_name   = "clk"
        platform.default_clk_period = 10.0
        fragment = Module().get_fragment()

        platform.finalize(fragment)

        self.assertTrue(platform.finalized)
        self.assertTrue(platform.use_default_clk)
        clk = platform.lookup_request("clk")
        self.assertEqual(platform.toolchain.clocks[clk], [10.0, None])
        with self.assertRaisesRegex(ConstraintError, "Already finalized"):
            platform.finalize(fragment)

    def test_bitstream_extension_variants(self):
        class StringExtPlatform(GenericPlatform):
            _bitstream_ext = ".bit"

        class DictExtPlatform(GenericPlatform):
            _bitstream_ext = {"sram": ".bit", "flash": ".bin"}

        self.assertIsNone(_make_platform().get_bitstream_extension())
        self.assertEqual(StringExtPlatform("dev", [], name="p").get_bitstream_extension("flash"), ".bit")
        self.assertEqual(DictExtPlatform("dev", [], name="p").get_bitstream_extension("flash"), ".bin")
        with self.assertRaises(KeyError):
            DictExtPlatform("dev", [], name="p").get_bitstream_extension("unsupported")

    def test_jtag_support_variants(self):
        class ListPlatform(GenericPlatform):
            _jtag_support = ["xc7", "ecp5"]

        self.assertTrue(_make_platform().jtag_support)
        self.assertTrue(ListPlatform("xc7a35t", [], name="p").jtag_support)
        self.assertFalse(ListPlatform("ice40", [], name="p").jtag_support)


class TestGenericToolchain(unittest.TestCase):
    def _assert_build_restores_cwd_on_failure(self, toolchain, message):
        platform = _make_platform(io=[])
        platform.toolchain = toolchain
        dut = Module()
        dut.clock_domains.cd_sys = ClockDomain("sys")
        cwd = os.getcwd()

        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaisesRegex(RuntimeError, message):
                toolchain.build(platform, dut, build_dir=os.path.join(tmp_dir, "build"), run=True)

        self.assertEqual(os.getcwd(), cwd)

    def test_period_constraint_ignores_none_and_can_skip_keep(self):
        toolchain = GenericToolchain()
        clk       = Signal()

        toolchain.add_period_constraint(None, None, 10.0)
        toolchain.add_period_constraint(None, clk, 5.0, keep=False, name="sys_clk")

        self.assertNotIn("keep", clk.attr)
        self.assertEqual(toolchain.clocks[clk], [5.0, "sys_clk"])

    def test_period_constraint_rounding_keep_and_conflict(self):
        toolchain = GenericToolchain()
        clk       = Signal()

        toolchain.add_period_constraint(None, clk, 10.1239)
        toolchain.add_period_constraint(None, clk, 10.123)

        self.assertEqual(toolchain.clocks[clk], [10.123, None])
        self.assertIn("keep", clk.attr)
        with self.assertRaisesRegex(ValueError, "Clock already constrained"):
            toolchain.add_period_constraint(None, clk, 11.0)

    def test_period_constraint_unwraps_proxied_signal(self):
        class _Proxy:
            def __init__(self):
                self.p = Signal()

        toolchain = GenericToolchain()
        clk       = _Proxy()

        toolchain.add_period_constraint(None, clk, 8.0)

        self.assertEqual(toolchain.clocks[clk.p], [8.0, None])
        self.assertIn("keep", clk.p.attr)

    def test_false_path_constraints_are_deduplicated_and_keep_signals(self):
        toolchain = GenericToolchain()
        a         = Signal()
        b         = Signal()

        toolchain.add_false_path_constraint(None, a, b)
        toolchain.add_false_path_constraint(None, a, b)

        self.assertEqual(toolchain.false_paths, {(a, b)})
        self.assertIn("keep", a.attr)
        self.assertIn("keep", b.attr)

    def test_false_path_constraints_can_skip_keep(self):
        toolchain = GenericToolchain()
        a         = Signal()
        b         = Signal()

        toolchain.add_false_path_constraint(None, a, b, keep=False)

        self.assertEqual(toolchain.false_paths, {(a, b)})
        self.assertNotIn("keep", a.attr)
        self.assertNotIn("keep", b.attr)

    def test_build_litex_backend_generates_verilog_project_and_script(self):
        platform = _make_platform(io=[])
        toolchain = _DummyToolchain()
        platform.toolchain = toolchain
        dut = Module()
        dut.clock_domains.cd_sys = ClockDomain("sys")

        with tempfile.TemporaryDirectory() as tmp_dir:
            build_dir = os.path.join(tmp_dir, "build")
            vns = toolchain.build(platform, dut, build_dir=build_dir, build_name="top", run=False)

            self.assertTrue(os.path.exists(os.path.join(build_dir, "top.v")))
            self.assertIs(toolchain._vns, vns)
            self.assertEqual(toolchain.finalize_calls, 1)
            self.assertEqual(toolchain.project_calls,  1)
            self.assertEqual(toolchain.script_calls,   1)
            self.assertEqual(toolchain.run_calls,      [])
            self.assertTrue(any(source[0] == os.path.join(build_dir, "top.v") for source in platform.sources))

    def test_build_litex_backend_runs_script_when_requested(self):
        platform = _make_platform(io=[])
        toolchain = _DummyToolchain()
        platform.toolchain = toolchain
        dut = Module()
        dut.clock_domains.cd_sys = ClockDomain("sys")

        with tempfile.TemporaryDirectory() as tmp_dir:
            toolchain.build(platform, dut, build_dir=os.path.join(tmp_dir, "build"), run=True)

        self.assertEqual(toolchain.run_calls, ["build.sh"])

    def test_build_restores_cwd_when_finalize_fails(self):
        platform  = _make_platform(io=[])
        toolchain = _DummyToolchain()
        dut       = Module()
        cwd       = os.getcwd()

        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(NotImplementedError):
                toolchain.build(platform, dut, build_dir=os.path.join(tmp_dir, "build"), run=False)

        self.assertEqual(os.getcwd(), cwd)

    def test_build_restores_cwd_when_timing_constraints_fail(self):
        class _FailingTimingToolchain(_DummyToolchain):
            def build_timing_constraints(self, vns):
                raise RuntimeError("timing failed")

        self._assert_build_restores_cwd_on_failure(_FailingTimingToolchain(), "timing failed")

    def test_build_restores_cwd_when_io_constraints_fail(self):
        class _FailingIOToolchain(_DummyToolchain):
            def build_io_constraints(self):
                raise RuntimeError("io failed")

        self._assert_build_restores_cwd_on_failure(_FailingIOToolchain(), "io failed")

    def test_build_restores_cwd_when_project_generation_fails(self):
        class _FailingProjectToolchain(_DummyToolchain):
            def build_project(self):
                raise RuntimeError("project failed")

        self._assert_build_restores_cwd_on_failure(_FailingProjectToolchain(), "project failed")

    def test_build_restores_cwd_when_script_generation_fails(self):
        class _FailingScriptToolchain(_DummyToolchain):
            def build_script(self):
                raise RuntimeError("script generation failed")

        self._assert_build_restores_cwd_on_failure(_FailingScriptToolchain(), "script generation failed")

    def test_build_restores_cwd_when_run_script_fails(self):
        class _FailingRunToolchain(_DummyToolchain):
            def run_script(self, script):
                raise RuntimeError("script failed")

        platform = _make_platform(io=[])
        toolchain = _FailingRunToolchain()
        platform.toolchain = toolchain
        dut = Module()
        dut.clock_domains.cd_sys = ClockDomain("sys")
        cwd = os.getcwd()

        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaisesRegex(RuntimeError, "script failed"):
                toolchain.build(platform, dut, build_dir=os.path.join(tmp_dir, "build"), run=True)

        self.assertEqual(os.getcwd(), cwd)

    def test_build_restores_cwd_when_backend_is_unsupported(self):
        platform = _make_platform(io=[])
        toolchain = _DummyToolchain()
        platform.toolchain = toolchain
        dut = Module()
        dut.clock_domains.cd_sys = ClockDomain("sys")
        cwd = os.getcwd()

        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(NotImplementedError):
                toolchain.build(
                    platform,
                    dut,
                    build_dir     = os.path.join(tmp_dir, "build"),
                    build_backend = "unsupported",
                    run           = False,
                )

        self.assertEqual(os.getcwd(), cwd)


if __name__ == "__main__":
    unittest.main()
