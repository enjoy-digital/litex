#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

from types import SimpleNamespace

import migen

from litex.build.efinix.efinity import EfinityToolchain, _get_design_file_library, build_argdict
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
    )

    params = build_argdict(args)

    assert params["efx_map_params"]["work_dir"] == "work_syn"
    assert params["efx_map_params"]["mode"] == ["area", "e_option"]
    assert params["efx_map_params"]["infer-sync-set-reset"] == ["0", "e_option"]
    assert params["efx_pnr_params"]["work_dir"] == "work_pnr"
    assert params["efx_pgm_params"]["generate_bitbin"] is True
    assert params["efx_pgm_params"]["generate_hexbin"] is False


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
        efx_full_memory_we=False,
    ) is sentinel

    assert toolchain._efx_map_params["work_dir"] == "work_syn"
    assert toolchain._efx_map_params["mode"] == ["area2", "e_option"]
    assert toolchain._efx_map_params["infer-sync-set-reset"] == ["1", "e_option"]
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
