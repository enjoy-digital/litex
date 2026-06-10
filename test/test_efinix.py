#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import xml.etree.ElementTree as et

from types import SimpleNamespace

import migen

from litex.build.efinix.efinity import (
    EfinityToolchain,
    _efinity_supports_unified_flow,
    _get_design_file_library,
    build_argdict,
)
from litex.build.efinix.common import add_gpio_block, efinix_special_overrides, gpio_info
from litex.build.efinix.ifacewriter import InterfaceWriter
from litex.build.efinix.toolchain import find_efinity_path, load_efinity_env
from litex.build.io import (
    ClkInput, ClkOutput,
    DDRInput, DDROutput, DDRTristate,
    DifferentialInput, DifferentialOutput,
    SDRInput, SDROutput, SDRTristate,
)
from litex.build.generic_toolchain import GenericToolchain
from litex.gen import LiteXContext
from litex.gen.fhdl import verilog
from litex.soc.cores.jtag import EfinixJTAG
from migen.fhdl.specials import Tristate


class _UnifiedEfinixPlatform:
    def __init__(self, family="Titanium"):
        self.family = family
        self.clks = {}
        self.toolchain = SimpleNamespace(unified=True)

    def get_pin_name(self, sig):
        return "pin"

    def get_pin_properties(self, sig):
        return [("PULL_OPTION", "WEAK_PULLUP")]


class _JTAGPins(SimpleNamespace):
    def flatten(self):
        return [
            self.CAPTURE, self.DRCK, self.RESET, self.RUNTEST, self.SEL, self.SHIFT,
            self.TCK, self.TDI, self.TMS, self.UPDATE, self.TDO,
        ]


class _LegacyEfinixJTAGPlatform:
    def __init__(self):
        self.toolchain = SimpleNamespace(
            unified=False,
            ifacewriter=InterfaceWriter("/tmp/efinity"),
            excluded_ios=[],
        )
        self._pins = _JTAGPins(
            CAPTURE=migen.Signal(name="capture"),
            DRCK=migen.Signal(name="drck"),
            RESET=migen.Signal(name="reset"),
            RUNTEST=migen.Signal(name="runtest"),
            SEL=migen.Signal(name="sel"),
            SHIFT=migen.Signal(name="shift"),
            TCK=migen.Signal(name="tck"),
            TDI=migen.Signal(name="tdi"),
            TMS=migen.Signal(name="tms"),
            UPDATE=migen.Signal(name="update"),
            TDO=migen.Signal(name="tdo"),
        )

    def add_extension(self, io):
        self.io = io

    def request(self, name):
        return self._pins


def _convert_unified_efinix(dut, ios, family="Titanium"):
    old_platform = LiteXContext.platform
    LiteXContext.platform = _UnifiedEfinixPlatform(family)
    try:
        return str(verilog.convert(dut, ios=ios, special_overrides=efinix_special_overrides))
    finally:
        LiteXContext.platform = old_platform


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
    monkeypatch.setattr("litex.build.efinix.efinity._efinity_supports_unified_flow", lambda path: True)

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


def test_build_rejects_unified_flow_without_efinity_support(monkeypatch):
    monkeypatch.setattr("litex.build.efinix.efinity._efinity_supports_unified_flow", lambda path: False)

    toolchain = EfinityToolchain("/tmp/efinity")
    platform = SimpleNamespace(family="Titanium")
    fragment = migen.Module().get_fragment()

    try:
        toolchain.build(platform, fragment, efx_unified=True, efx_full_memory_we=False)
    except OSError as e:
        assert "unified netlist flow" in str(e)
    else:
        raise AssertionError("Expected unsupported unified Efinity flow to be rejected")


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


def test_efinity_supports_unified_flow_detects_map_options(tmp_path):
    efinity_root = tmp_path / "efinity"
    (efinity_root / "bin").mkdir(parents=True)
    (efinity_root / "scripts").mkdir()
    (efinity_root / "bin" / "efx_map_options.xml").write_text(
        '<efx:option name="--peri-syn-instantiation"/>\n'
        '<efx:option name="--peri-syn-inference"/>\n'
    )
    (efinity_root / "scripts" / "efx_run.py").write_text("--un_flow\n--peri_netlist\n")

    assert _efinity_supports_unified_flow(str(efinity_root)) is True


def test_efinity_supports_unified_flow_rejects_old_map_options(tmp_path):
    efinity_root = tmp_path / "efinity"
    (efinity_root / "bin").mkdir(parents=True)
    (efinity_root / "scripts").mkdir()
    (efinity_root / "bin" / "efx_map_options.xml").write_text("")
    (efinity_root / "scripts" / "efx_run.py").write_text("--un_flow\n")

    assert _efinity_supports_unified_flow(str(efinity_root)) is False


def test_unified_efinix_clock_io_lowers_to_hdl_primitives():
    dut = migen.Module()
    clk_i = migen.Signal()
    clk_o = migen.Signal()
    pad_o = migen.Signal()
    dut.specials += [
        ClkInput(clk_i, clk_o),
        ClkOutput(clk_o, pad_o),
    ]

    v = _convert_unified_efinix(dut, {clk_i, clk_o, pad_o})

    assert "EFX_IBUF" in v
    assert "EFX_OBUF" in v


def test_unified_efinix_differential_io_lowers_to_lvds_primitives():
    for family, tx_primitive, rx_primitive in [
        ("Trion",    "EFX_LVDS_TX_V1", "EFX_LVDS_RX_V1"),
        ("Titanium", "EFX_LVDS_TX_V2", "EFX_LVDS_RX_V2"),
    ]:
        dut = migen.Module()
        tx_i = migen.Signal()
        tx_p = migen.Signal()
        tx_n = migen.Signal()
        rx_p = migen.Signal()
        rx_n = migen.Signal()
        rx_o = migen.Signal()
        dut.specials += [
            DifferentialOutput(tx_i, tx_p, tx_n),
            DifferentialInput(rx_p, rx_n, rx_o),
        ]

        v = _convert_unified_efinix(dut, {tx_i, tx_p, tx_n, rx_p, rx_n, rx_o}, family=family)

        assert f"\n{tx_primitive} #(" in v
        assert f"\n{rx_primitive} #(" in v


def test_unified_efinix_jtag_lowers_to_hdl_primitive():
    platform = _UnifiedEfinixPlatform()
    dut = EfinixJTAG(platform, id=2)

    v = str(verilog.convert(dut, ios={dut.tck, dut.tms, dut.tdi, dut.tdo}))

    assert "\nEFX_JTAG_V1 #(" in v
    assert '.RESOURCE ("JTAG_USER2")' in v


def test_legacy_efinix_jtag_lowers_to_ifacewriter_block():
    platform = _LegacyEfinixJTAGPlatform()
    dut = EfinixJTAG(platform, id=3)

    str(verilog.convert(dut, ios={dut.tck, dut.tms, dut.tdi, dut.tdo}))

    assert len(platform.toolchain.ifacewriter.blocks) == 1
    assert platform.toolchain.ifacewriter.blocks[0]["type"] == "JTAG"
    assert platform.toolchain.ifacewriter.blocks[0]["id"] == 3
    assert len(platform.toolchain.excluded_ios) == 11


def test_unified_efinix_tristate_lowers_to_hdl_io_buffers():
    dut = migen.Module()
    io = migen.Signal(2)
    o  = migen.Signal(2)
    oe = migen.Signal(2)
    i  = migen.Signal(2)
    dut.specials += Tristate(io, o, oe, i)

    v = _convert_unified_efinix(dut, {io, o, oe, i})

    assert v.count("\nEFX_IO_BUF #(") == 2


def test_unified_efinix_registered_io_lowers_to_hdl_primitives():
    dut = migen.Module()
    clk = migen.Signal()
    sdr_i = migen.Signal(2)
    sdr_o = migen.Signal(2)
    ddr_i = migen.Signal(2)
    ddr_o1 = migen.Signal(2)
    ddr_o2 = migen.Signal(2)
    ddr_i1 = migen.Signal(2)
    ddr_i2 = migen.Signal(2)
    ddr_o = migen.Signal(2)
    dut.specials += [
        SDRInput(sdr_i, sdr_o, clk),
        SDROutput(sdr_o, sdr_i, clk),
        DDRInput(ddr_i, ddr_o1, ddr_o2, clk),
        DDROutput(ddr_i1, ddr_i2, ddr_o, clk),
    ]

    v = _convert_unified_efinix(dut, {
        clk, sdr_i, sdr_o, ddr_i, ddr_o1, ddr_o2, ddr_i1, ddr_i2, ddr_o,
    })

    assert v.count("\nEFX_IREG #(") == 2
    assert v.count("\nEFX_OREG #(") == 2
    assert v.count("\nEFX_IDDIO #(") == 2
    assert v.count("\nEFX_ODDIO #(") == 2


def test_unified_efinix_sdr_tristate_lowers_to_hdl_ioreg():
    dut = migen.Module()
    clk = migen.Signal()
    io  = migen.Signal(2)
    o   = migen.Signal(2)
    oe  = migen.Signal(2)
    i   = migen.Signal(2)
    dut.specials += SDRTristate(io, o, oe, i, clk)

    v = _convert_unified_efinix(dut, {clk, io, o, oe, i})

    assert v.count("\nEFX_IOREG #(") == 2


def test_unified_efinix_ddr_tristate_uses_family_gpio_primitive():
    for family, primitive in [("Trion", "EFX_GPIO_V2"), ("Titanium", "EFX_GPIO_V3")]:
        dut = migen.Module()
        clk = migen.Signal()
        io  = migen.Signal(2)
        o1  = migen.Signal(2)
        o2  = migen.Signal(2)
        oe  = migen.Signal(2)
        i1  = migen.Signal(2)
        i2  = migen.Signal(2)
        dut.specials += DDRTristate(io, o1, o2, oe, i1=i1, i2=i2, clk=clk)

        v = _convert_unified_efinix(dut, {clk, io, o1, o2, oe, i1, i2}, family=family)

        assert v.count(f"\n{primitive} #(") == 2


def test_unified_io_constraints_write_isf_assignments(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    skip_signal = migen.Signal(name="skip_signal")
    toolchain = EfinityToolchain("/tmp/efinity")
    toolchain.unified = True
    toolchain._build_name = "top"
    toolchain.named_sc = [
        ("clk", ["P1"], [], ("clk", 0, None)),
        ("led", ["P2", "P3"], [], ("led", 0, None)),
        ("skip", ["P4"], [], ("skip", 0, None)),
        ("skip_signal", ["P5"], [], ("skip_signal", 0, None)),
    ]
    toolchain.named_pc = []
    toolchain.excluded_ios = ["skip", skip_signal]
    toolchain.platform = SimpleNamespace(iobank_info=[("BANK0", "3.3_V_LVCMOS")], device="Ti60F225")
    toolchain.ifacewriter.blocks = []

    assert toolchain.build_io_constraints() == ("top.isf", "ISF")

    isf = (tmp_path / "top.isf").read_text()
    assert 'design.set_iobank_voltage("BANK0", "3.3")' in isf
    assert 'design.assign_pkg_pin("clk","P1")' in isf
    assert 'design.assign_pkg_pin("led[0]","P2")' in isf
    assert 'design.assign_pkg_pin("led[1]","P3")' in isf
    assert "skip" not in isf
    assert "skip_signal" not in isf


def test_unified_timing_constraints_use_pll_output_clocks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def signal_name(sig):
        return sig.backtrace[-1][0]

    clk25 = migen.Signal(name="clk25")
    hard_clk = migen.Signal(name="hard_pll_clk")
    toolchain = EfinityToolchain("/tmp/efinity")
    toolchain.unified = True
    toolchain._build_name = "top"
    toolchain._vns = SimpleNamespace(get_name=signal_name)
    toolchain.clocks = {clk25: [40.0, None]}
    toolchain.false_paths = set()
    toolchain.named_sc = [
        ("clk25", ["P1"], [], ("clk25", 0, None)),
        ("sys_pll0_clk", ["X"], [], ("sys_pll0_clk", 0, None)),
        ("hard_pll_clk", ["X"], [], ("hard_pll_clk", 0, None)),
    ]
    toolchain.excluded_ios = [clk25, hard_clk]
    toolchain.additional_sdc_commands = []
    toolchain.ifacewriter.blocks = [{
        "type"    : "PLL",
        "name"    : "pll0",
        "clk_out" : [
            ["sys_pll0_clk", 50e6, 0, 0, False],
            ["hard_pll_clk", 200e6, 0, 0, False],
            ["unused_pll_clk", 100e6, 0, 0, False],
        ],
    }]

    assert toolchain.build_timing_constraints(None) == ("top.sdc", "SDC")

    sdc = (tmp_path / "top.sdc").read_text()
    assert "clk25" not in sdc
    assert "hard_pll_clk" not in sdc
    assert "unused_pll_clk" not in sdc
    assert "create_clock -name sys_pll0_clk -period 20.0 [get_ports {sys_pll0_clk}]" in sdc


def test_unified_io_constraints_write_mixed_iface_isf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    toolchain = EfinityToolchain("/tmp/efinity")
    toolchain.unified = True
    toolchain._build_name = "top"
    toolchain.named_sc = []
    toolchain.named_pc = []
    toolchain.platform = SimpleNamespace(iobank_info=None, device="Ti60F225")
    toolchain.ifacewriter.blocks = [{
        "type"   : "SEU",
        "name"   : "seu",
        "pins"   : SimpleNamespace(),
        "enable" : False,
        "mode"   : "auto",
    }]

    assert toolchain.build_io_constraints() == ("top.isf", "ISF")

    assert toolchain._unified_iface_file == "iface.isf"
    assert 'design.set_device_property("seu", "ENA_DETECT", "False", "SEU")' in (tmp_path / "iface.isf").read_text()


def test_unified_io_constraints_write_importable_pll_isf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    toolchain = EfinityToolchain("/tmp/efinity")
    toolchain.unified = True
    toolchain._build_name = "top"
    toolchain.named_sc = []
    toolchain.named_pc = []
    toolchain.platform = SimpleNamespace(iobank_info=None, device="Ti60F225")
    toolchain.ifacewriter.blocks = [{
        "type"         : "PLL",
        "name"         : "pll0",
        "input_freq"   : 25e6,
        "input_clock"  : "INTERNAL",
        "input_signal" : "clk25",
        "resource"     : "PLL_BL0",
        "locked"       : "pll0_locked",
        "rstn"         : "pll0_rstn",
        "version"      : "V3",
        "feedback"     : -1,
        "clk_out"      : [["sys_clk", 100e6, 0, 0, False], None, None, None, None],
    }]

    assert toolchain.build_io_constraints() == ("top.isf", "ISF")

    iface = (tmp_path / "iface.isf").read_text()
    assert 'design.create_block("pll0", block_type="PLL")' in iface
    assert 'design.auto_calc_pll_clock("pll0", {' in iface
    assert "'CLKOUT0_FREQ': '100.0'" in iface
    assert "target_freq = {" not in iface
    assert "for c in calc_result" not in iface


def test_unified_io_constraints_write_hard_ip_iface_isf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def sig(name, nbits=1):
        return migen.Signal(nbits, name=name)

    hyperram_pads = SimpleNamespace(
        clkp_h   = sig("hyperram_clkp_h"),
        clkp_l   = sig("hyperram_clkp_l"),
        clkn_h   = sig("hyperram_clkn_h"),
        clkn_l   = sig("hyperram_clkn_l"),
        dq_o_h   = sig("hyperram_dq_o_h", 16),
        dq_o_l   = sig("hyperram_dq_o_l", 16),
        dq_i_h   = sig("hyperram_dq_i_h", 16),
        dq_i_l   = sig("hyperram_dq_i_l", 16),
        dq_oe    = sig("hyperram_dq_oe", 16),
        rwds_o_h = sig("hyperram_rwds_o_h", 2),
        rwds_o_l = sig("hyperram_rwds_o_l", 2),
        rwds_i_h = sig("hyperram_rwds_i_h", 2),
        rwds_i_l = sig("hyperram_rwds_i_l", 2),
        rwds_oe  = sig("hyperram_rwds_oe", 2),
        csn      = sig("hyperram_csn"),
        rstn     = sig("hyperram_rstn"),
    )
    spiflash_pads = SimpleNamespace(
        cs_n = sig("spiflash_cs_n"),
        clk  = sig("spiflash_clk"),
        mosi = sig("spiflash_mosi"),
        miso = sig("spiflash_miso"),
        wp   = sig("spiflash_wp"),
        hold = sig("spiflash_hold"),
    )

    toolchain = EfinityToolchain("/tmp/efinity")
    toolchain.unified = True
    toolchain._build_name = "top"
    toolchain.named_sc = []
    toolchain.named_pc = []
    toolchain.platform = SimpleNamespace(iobank_info=None, device="Ti60F225")
    toolchain.ifacewriter.blocks = [
        {
            "type"      : "HYPERRAM",
            "name"      : "hp_inst",
            "location"  : "HYPER_RAM0",
            "pads"      : hyperram_pads,
            "ctl_clk"   : sig("hp_clk"),
            "cal_clk"   : sig("hp_cal_clk"),
            "clk90_clk" : sig("hp_clk90"),
        },
        {
            "type"     : "SPI_FLASH",
            "name"     : "flash",
            "location" : "SPI_FLASH0",
            "mode"     : "x1",
            "pads"     : spiflash_pads,
        },
        {
            "type"      : "MIPI_TX_LANE",
            "name"      : "mipi_tx",
            "mode"      : "HS",
            "props"     : {"TX_PROP": "1"},
            "ressource" : "MIPI_TX0",
        },
        {
            "type"      : "MIPI_RX_LANE",
            "name"      : "mipi_rx",
            "mode"      : "HS",
            "props"     : {"RX_PROP": "1"},
            "ressource" : "MIPI_RX0",
        },
        {
            "type"         : "REMOTE_UPDATE",
            "name"         : "ru",
            "pins"         : SimpleNamespace(),
            "clock"        : "sys_clk",
            "invert_clock" : False,
            "enable"       : False,
        },
    ]

    assert toolchain.build_io_constraints() == ("top.isf", "ISF")

    iface = (tmp_path / "iface.isf").read_text()
    assert 'design.create_block("hp_inst", "HYPERRAM")' in iface
    assert 'design.set_property("hp_inst", "CS_N_PIN",        "hyperram_csn", "HYPERRAM")' in iface
    assert 'design.assign_resource("hp_inst", "HYPER_RAM0", "HYPERRAM")' in iface
    assert 'design.create_block("flash", "SPI_FLASH")' in iface
    assert 'design.set_property("flash", "MOSI_OUT_PIN",   "spiflash_mosi", "SPI_FLASH")' in iface
    assert 'design.assign_resource("flash", "SPI_FLASH0","SPI_FLASH")' in iface
    assert 'design.create_block("mipi_tx","MIPI_TX_LANE", mode="HS")' in iface
    assert 'design.assign_resource("mipi_rx","MIPI_RX0","MIPI_RX_LANE")' in iface
    assert 'design.set_device_property("ru", "RECONFIG_EN", "False", "RU")' in iface


def test_unified_io_constraints_reject_non_importable_iface_blocks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    toolchain = EfinityToolchain("/tmp/efinity")
    toolchain.unified = True
    toolchain._build_name = "top"
    toolchain.named_sc = []
    toolchain.named_pc = []
    toolchain.platform = SimpleNamespace(iobank_info=None, device="Ti60F225")
    toolchain.ifacewriter.blocks = [{"type": "GPIO", "name": "gpio0"}]

    try:
        toolchain.build_io_constraints()
    except NotImplementedError as e:
        assert "GPIO" in str(e)
    else:
        raise AssertionError("Expected non-importable InterfaceWriter block to be rejected")


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
    toolchain._unified_iface_file = "iface.isf"
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
    assert [e.get("name") for e in root.findall("efx:isf_info/efx:isf_file", ns)] == ["top.isf", "iface.isf"]
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
