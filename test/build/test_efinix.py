#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

from types import SimpleNamespace
import xml.etree.ElementTree as et

import migen
import pytest

from litex.build.efinix.efinity import EfinityToolchain, _add_verilog_include_paths
from litex.build.efinix.efinity import _get_design_file_library, build_argdict
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


def test_verilog_include_paths_emit_efx_include_params():
    efx_map = et.Element("efx:synthesis", {"tool_name": "efx_map"})

    _add_verilog_include_paths(efx_map, ["/rtl/include0", "/rtl/include1"])

    params = [
        (param.get("name"), param.get("value"), param.get("value_type"))
        for param in efx_map.findall("efx:param")
    ]

    assert params == [
        ("include", "/rtl/include0", "e_string"),
        ("include", "/rtl/include1", "e_string"),
    ]


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


@pytest.mark.parametrize("partnumber, with_feedback_mode", [
    ("T4F49",  False),
    ("T8F81",  False),
    ("T8Q144",  True),
    ("T20F256", True),
])
def test_generate_pll_handles_trion_v1_feedback_mode(partnumber, with_feedback_mode):
    writer = InterfaceWriter("/tmp/efinity")
    block = {
        "name"         : "pll0",
        "input_freq"   : 33.333e6,
        "input_clock"  : "CORE",
        "input_signal" : "clk",
        "resource"     : "PLL_0",
        "locked"       : "locked",
        "rstn"         : "rstn",
        "clk_out"      : [["sys_clk", 33.333e6, 0, 0, False]],
        "feedback"     : -1,
        "version"      : "V1_V2",
    }

    cmds = writer.generate_pll(block, partnumber, verbose=False)
    feedback_mode_cmd = 'design.set_property("pll0","FEEDBACK_MODE","INTERNAL","PLL")'

    assert (feedback_mode_cmd in cmds) is with_feedback_mode
    assert 'design.auto_calc_pll_clock("pll0", target_freq)' in cmds


def test_generate_ddr_emits_controller_interfaces_and_swizzle():
    def signal(name):
        return migen.Signal(name_override=name)

    axi_names = [
        "araddr", "arapcmd", "arburst", "arid", "arlen", "arlock", "arqos", "arready",
        "arsize", "resetn", "arvalid", "awaddr", "awallstrb", "awapcmd", "awburst",
        "awcache", "awcobuf", "awid", "awlen", "awlock", "awqos", "awready", "awsize",
        "awvalid", "bid", "bready", "bresp", "bvalid", "rdata", "rid", "rlast", "rready",
        "rresp", "rvalid", "wdata", "wlast", "wready", "wstrb", "wvalid",
    ]
    writer = InterfaceWriter("/tmp/efinity")
    writer.blocks.append({
        "type"            : "DDR",
        "name"            : "ddr_inst1",
        "location"        : "DDR_0",
        "memory_type"     : "LPDDR4x",
        "memory_density"  : "8G",
        "dq_width"        : 32,
        "physical_rank"   : 1,
        "clkin_sel"       : "CLKIN 0",
        "axi"             : SimpleNamespace(**{name: signal(f"ddr0_{name}") for name in axi_names}),
        "axi_clk"         : "sys_pll0_clk",
        "axi_data_width"  : 512,
        "cfg"             : SimpleNamespace(
            done  = signal("cfg_done"),
            reset = signal("cfg_reset"),
            sel   = signal("cfg_sel"),
            start = signal("cfg_start"),
        ),
        "pin_swizzle" : {
            "CA"   : "CA[0],CA[1],CA[2],CA[3],CA[4],CA[5]",
            "DQM0" : "DQ[3],DQ[6],DQ[4],DQ[5],DQ[0],DQ[1],DQ[7],DQ[2],DM[0]",
        },
    })

    cmds = writer.generate(partnumber="Ti375C529")

    assert 'design.create_block("ddr_inst1", "DDR")' in cmds
    assert '"MEMORY_TYPE", "LPDDR4x", "DDR"' in cmds
    assert '"AXI0_ARADDR_BUS", "ddr0_araddr", "DDR"' in cmds
    assert '"AXI0_AWALLSTRB_PIN", "ddr0_awallstrb", "DDR"' in cmds
    assert '"AXI0_CLK_INPUT_PIN", "sys_pll0_clk", "DDR"' in cmds
    assert '"CFG_DONE_PIN", "cfg_done", "DDR"' in cmds
    assert '"CTRL_BUSY_PIN", "", "DDR"' in cmds
    assert '"PIN_SWIZZLE_DQM0", "DQ[3],DQ[6],DQ[4],DQ[5],DQ[0],DQ[1],DQ[7],DQ[2],DM[0]", "DDR"' in cmds
    assert '"PIN_SWIZZLE_EN", "1", "DDR"' in cmds
    assert 'design.assign_resource("ddr_inst1", "DDR_0", "DDR")' in cmds


def test_find_efinity_path_prefers_env(monkeypatch, tmp_path):
    efinity_root = tmp_path / "efinity"
    bin_dir = efinity_root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "setup.sh").write_text("export TEST_EFINITY_ENV=from_env\n")
    monkeypatch.setenv("LITEX_ENV_EFINITY", str(efinity_root) + "/")

    assert find_efinity_path() == str(efinity_root)


def test_find_efinity_path_rejects_invalid_env(monkeypatch, tmp_path):
    efinity_root = tmp_path / "efinity"
    monkeypatch.setenv("LITEX_ENV_EFINITY", str(efinity_root) + "/")

    with pytest.raises(OSError):
        find_efinity_path()


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
