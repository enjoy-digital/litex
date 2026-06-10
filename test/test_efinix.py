#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import xml.etree.ElementTree as et

from types import SimpleNamespace

import migen

from litex.build.efinix.efinity import EfinityToolchain, _get_design_file_library, build_argdict
from litex.build.efinix.common import add_gpio_block, gpio_info
from litex.build.efinix.ifacewriter import InterfaceWriter
from litex.build.efinix.toolchain import find_efinity_path, load_efinity_env
from litex.build.generic_toolchain import GenericToolchain


def test_build_argdict_wires_infer_sync_set_reset():
    args = SimpleNamespace(
        synth_mode="area",
        infer_clk_enable="2",
        infer_sync_set_reset="0",
        bram_output_regs_packing="1",
        retiming="2",
        seq_opt="0",
        mult_input_regs_packing="1",
        mult_output_regs_packing="0",
        generate_bitbin=True,
        generate_hexbin=False,
        efinity_unified=True,
    )

    params = build_argdict(args)

    assert params["efx_map_params"]["work_dir"] == "work_syn"
    assert params["efx_map_params"]["mode"] == ["area", "e_option"]
    assert params["efx_map_params"]["infer-sync-set-reset"] == ["0", "e_option"]
    assert params["efx_pnr_params"]["work_dir"] == "work_pnr"
    assert params["efx_pgm_params"]["generate_bitbin"] is True
    assert params["efx_pgm_params"]["generate_hexbin"] is False
    assert params["efx_unified"] is True


def test_build_merges_default_efinity_params(monkeypatch):
    sentinel = object()

    def fake_build(self, platform, fragment, **kwargs):
        return sentinel

    monkeypatch.setattr(GenericToolchain, "build", fake_build)

    toolchain = EfinityToolchain("/tmp/efinity")
    platform = SimpleNamespace(family="Titanium")
    fragment = migen.Module().get_fragment()

    assert toolchain.build(
        platform,
        fragment,
        efx_map_params={"mode": ["area2", "e_option"]},
        efx_pgm_params={"generate_bitbin": True},
        efx_unified=True,
        efx_full_memory_we=False,
    ) is sentinel

    assert toolchain._efx_map_params["work_dir"] == "work_syn"
    assert toolchain._efx_map_params["mode"] == ["area2", "e_option"]
    assert toolchain._efx_map_params["infer-sync-set-reset"] == ["1", "e_option"]
    assert toolchain._efx_map_params["write_efx_verilog"] is True
    assert toolchain._efx_map_params["peri-syn-instantiation"] == ["1", "e_option"]
    assert toolchain._efx_map_params["peri-syn-inference"] == ["1", "e_option"]
    assert toolchain._efx_map_params["peri-syn-modify-vdb-module-name"] == ["1", "e_option"]
    assert "mult_input_regs_packing" not in toolchain._efx_map_params
    assert "mult_output_regs_packing" not in toolchain._efx_map_params
    assert toolchain._efx_pnr_params["work_dir"] == "work_pnr"
    assert toolchain._efx_pgm_params["generate_bitbin"] is True
    assert toolchain._efx_pgm_params["generate_hexbin"] is False


def test_design_file_library_preserves_non_header_libraries():
    assert _get_design_file_library("core.vhd", "worklib") == "worklib"
    assert _get_design_file_library("rtl/top.v", "mylib") == "mylib"
    assert _get_design_file_library("rtl/header.vh", "mylib") == "default"
    assert _get_design_file_library("rtl/header.svh", "mylib") == "default"


def test_design_file_library_uses_default_library_for_verilog_languages():
    assert _get_design_file_library("rtl/top.v", "verilog", "mylib") == "default"
    assert _get_design_file_library("rtl/header.vh", "verilog", "mylib") == "default"
    assert _get_design_file_library("rtl/header.svh", "systemverilog", "mylib") == "default"
    assert _get_design_file_library("core.vhd", "vhdl", "worklib") == "worklib"


def test_unified_io_constraints_write_isf_assignments(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    toolchain = EfinityToolchain("/tmp/efinity")
    toolchain.unified = True
    toolchain._build_name = "top"
    toolchain.named_sc = [
        ("clk", ["P1"], [], ("clk", 0, None)),
        ("led", ["P2", "P3"], [], ("led", 0, None)),
    ]
    toolchain.named_pc = []
    toolchain.ifacewriter.blocks = []

    assert toolchain.build_io_constraints() == ("top.isf", "ISF")

    isf = (tmp_path / "top.isf").read_text()
    assert 'design.assign_pkg_pin("clk","P1")' in isf
    assert 'design.assign_pkg_pin("led[0]","P2")' in isf
    assert 'design.assign_pkg_pin("led[1]","P3")' in isf


def test_unified_project_references_isf_and_litex_sdc(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    efinity_root = tmp_path / "efinity"
    (efinity_root / "scripts").mkdir(parents=True)
    (efinity_root / "bin").mkdir()
    (efinity_root / "scripts" / "sw_version.txt").write_text("2025.1\n")
    (efinity_root / "bin" / "setup.sh").write_text("export EFINITY_TEST_ENV=1\n")

    toolchain = EfinityToolchain(str(efinity_root))
    toolchain.unified = True
    toolchain._build_name = "top"
    toolchain._unified_isf_file = "top.isf"
    toolchain._efx_map_params = {
        "work_dir": "work_syn",
        "peri-syn-instantiation": ["1", "e_option"],
    }
    toolchain._efx_pnr_params = {"work_dir": "work_pnr"}
    toolchain._efx_pgm_params = {}
    toolchain._efx_debugger_params = {}
    toolchain._efx_security_params = {}
    toolchain.platform = SimpleNamespace(
        family="Titanium",
        device="Ti60F225",
        timing_model="C4",
        sources=[("top.v", "verilog", "default")],
        spi_mode="active",
        spi_width="1",
    )

    toolchain.build_project()

    ns = {"efx": "http://www.efinixinc.com/enf_proj"}
    root = et.parse(tmp_path / "top.xml").getroot()
    assert root.find("efx:constraint_info/efx:sdc_file", ns).get("name") == "top.sdc"
    assert root.find("efx:isf_info/efx:isf_file", ns).get("name") == "top.isf"
    assert root.find("efx:synthesis/efx:param[@name='peri-syn-instantiation']", ns).get("value") == "1"


def test_unified_run_script_passes_un_flow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "outflow").mkdir()
    (tmp_path / "top.sdc").write_text("")

    calls = []

    def fake_call(cmd, *args, **kwargs):
        calls.append(cmd)
        return 0

    monkeypatch.setattr("litex.build.tools.subprocess_call_filtered", fake_call)

    toolchain = EfinityToolchain("/tmp/efinity")
    toolchain.unified = True
    toolchain.env = {}
    toolchain._build_name = "top"
    toolchain._build_dir = str(tmp_path)

    toolchain.run_script(None)

    assert calls
    assert "--un_flow" in calls[0]
    assert not (tmp_path / "top_merged.sdc").exists()


def test_gpio_info_handles_scalar_and_vector_signals():
    class Platform:
        def get_pin_name(self, sig):
            return "scalar"

        def get_pin_location(self, sig):
            return ["P1"]

        def get_pins_name(self, sig):
            return "vector"

        def get_pins_location(self, sig):
            return ["P1", "P2"]

        def get_pin_properties(self, sig):
            return [("IO_STANDARD", "3.3_V_LVCMOS")]

    scalar = migen.Signal()
    vector = migen.Signal(2)

    assert gpio_info(Platform(), scalar) == (
        "scalar",
        ["P1"],
        [("IO_STANDARD", "3.3_V_LVCMOS")],
    )
    assert gpio_info(Platform(), vector) == (
        "vector",
        ["P1", "P2"],
        [("IO_STANDARD", "3.3_V_LVCMOS")],
    )


def test_add_gpio_block_tracks_block_and_excluded_io():
    sig = migen.Signal()
    block = {"type": "GPIO", "name": "gpio"}
    platform = SimpleNamespace(
        toolchain=SimpleNamespace(ifacewriter=SimpleNamespace(blocks=[]), excluded_ios=[]),
        get_pin=lambda sig: "resolved-pin",
    )

    add_gpio_block(platform, block, sig)

    assert platform.toolchain.ifacewriter.blocks == [block]
    assert platform.toolchain.excluded_ios == ["resolved-pin"]


def test_generate_seu_emits_wait_interval_for_auto_mode():
    def pin(name):
        return SimpleNamespace(backtrace=[(name, None)])

    writer = InterfaceWriter("/tmp/efinity")
    pins = SimpleNamespace(
        CONFIG       = pin("config"),
        DONE         = pin("done"),
        ERROR        = pin("error"),
        INJECT_ERROR = pin("inject_error"),
        RST          = pin("rst"),
    )
    block = {
        "name"          : "seu",
        "pins"          : pins,
        "enable"        : True,
        "mode"          : "auto",
        "wait_interval" : "42",
    }

    cmds = writer.generate_seu(block)

    assert 'MODE", "AUTO"' in cmds
    assert 'WAIT_INTERVAL", "42"' in cmds


def test_find_efinity_path_prefers_env(monkeypatch, tmp_path):
    efinity_root = tmp_path / "efinity"
    monkeypatch.setenv("LITEX_ENV_EFINITY", str(efinity_root) + "/")

    assert find_efinity_path() == str(efinity_root)


def test_find_efinity_path_falls_back_to_path(monkeypatch, tmp_path):
    efinity_root = tmp_path / "efinity"
    bin_dir = efinity_root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "setup.sh").write_text("export TEST_EFINITY_ENV=from_path\n")
    tool = bin_dir / "efx_map"
    tool.write_text("#!/bin/sh\n")
    tool.chmod(0o755)

    monkeypatch.delenv("LITEX_ENV_EFINITY", raising=False)
    monkeypatch.setenv("PATH", str(bin_dir))

    assert find_efinity_path() == str(efinity_root)


def test_load_efinity_env_sources_setup(tmp_path):
    efinity_root = tmp_path / "efinity"
    bin_dir = efinity_root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "setup.sh").write_text("export TEST_EFINITY_ENV=loaded\n")

    env = load_efinity_env(str(efinity_root))

    assert env["TEST_EFINITY_ENV"] == "loaded"
