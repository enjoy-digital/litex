#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import migen
import pytest

from litex.build.vhd2v_converter import VHD2VConverter


class _DummyPlatform:
    support_mixed_language = True
    output_dir = "/tmp"

    def __init__(self):
        self.sources = []

    def add_source(self, path, library=None):
        self.sources.append((path, library))


def test_constructor_aliases_map_to_legacy_fields():
    platform = _DummyPlatform()
    dut = VHD2VConverter(
        platform   = platform,
        name       = "core_top",
        output_dir = "/tmp/build",
        ports      = {"i_data": migen.Signal()},
        sources    = ["core.vhd"],
        library    = "worklib",
    )

    assert dut._top_entity == "core_top"
    assert dut._build_dir == "/tmp/build"
    assert dut._work_package == "worklib"
    assert dut._sources == ["core.vhd"]
    assert "i_data" in dut._params
    assert dut._add_instance is True


def test_constructor_alias_conflicts_are_rejected():
    platform = _DummyPlatform()

    with pytest.raises(ValueError):
        VHD2VConverter(platform, top_entity="a", name="b")

    with pytest.raises(ValueError):
        VHD2VConverter(platform, build_dir="/tmp/a", output_dir="/tmp/b")

    with pytest.raises(ValueError):
        VHD2VConverter(platform, work_package="a", library="b")

    with pytest.raises(ValueError):
        VHD2VConverter(platform, files=["a.vhd"], sources=["b.vhd"])

    with pytest.raises(ValueError):
        VHD2VConverter(platform, params={"i_a": 1}, ports={"i_b": 2})


def test_normalize_instance_ports_valid_and_generic_passthrough():
    platform = _DummyPlatform()
    dut = VHD2VConverter(platform, top_entity="top")

    params = {
        "i_data"     : migen.Signal(),
        "o__bus_pull": migen.Signal(),
        "io_pad"     : migen.Signal(),
        "p_WIDTH"    : 32,
    }
    normalized = dut._normalize_instance_ports(params)
    assert set(normalized.keys()) == {"i_data", "o__bus_pull", "io_pad"}

    generics = dut._extract_generics(params)
    assert generics == ["-gWIDTH=32"]


def test_normalize_instance_ports_invalid():
    platform = _DummyPlatform()
    dut = VHD2VConverter(platform, top_entity="my_top")

    with pytest.raises(ValueError) as e:
        dut._normalize_instance_ports({"badkey": migen.Signal()})

    assert "Invalid VHD2V port 'badkey'" in str(e.value)
    assert "my_top" in str(e.value)


def test_normalize_instance_ports_distinguishes_escaped_names():
    platform = _DummyPlatform()
    dut = VHD2VConverter(platform, top_entity="top")

    params = dut._normalize_instance_ports({
        "i_data":  migen.Signal(),
        "i__data": migen.Signal(),
    })
    assert set(params.keys()) == {"i_data", "i__data"}


def test_do_finalize_mixed_language_with_ports():
    platform = _DummyPlatform()
    sig = migen.Signal()
    dut = VHD2VConverter(
        platform = platform,
        name     = "core_top",
        ports    = {"i_data": sig},
        sources  = ["core.vhd"],
    )

    dut.do_finalize()

    assert ("core.vhd", None) in platform.sources


def test_sanitize_ghdl_escaped_identifiers():
    text = "module top; wire \\foo.bar ; wire \\baz$1\t; endmodule\n"
    out = VHD2VConverter._sanitize_ghdl_escaped_identifiers(text)
    assert "\\foo.bar" not in out
    assert "\\baz$1" not in out
    assert "ghdl_foo.bar " in out
    assert "ghdl_baz$1\t" in out
