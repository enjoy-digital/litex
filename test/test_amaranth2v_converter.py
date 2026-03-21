#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import pytest
import migen

amaranth = pytest.importorskip("amaranth")

pytestmark = [pytest.mark.unit, pytest.mark.optional]

from litex.build.amaranth2v_converter import Amaranth2VConverter


class _DummyPlatform:
    output_dir = "/tmp"

    def add_source(self, _path):
        pass


def _converter(core_params=None, module=None):
    return Amaranth2VConverter(
        platform=_DummyPlatform(),
        module=module,
        ports=core_params or {},
        output_dir="/tmp",
    )


def test_constructor_aliases_map_to_canonical_fields():
    sig = migen.Signal()

    dut = Amaranth2VConverter(
        platform=_DummyPlatform(),
        module  = amaranth.Module(),
        core_params={"i_data": sig},
        clock_domains=["usb"],
        output_dir = "/tmp",
    )

    assert dut.ports["i_data"] is sig
    assert dut.core_params["i_data"] is sig
    assert "sync" in dut.m._domains
    assert "usb" in dut.m._domains


def test_constructor_alias_conflicts_are_rejected():
    with pytest.raises(ValueError):
        Amaranth2VConverter(
            platform=_DummyPlatform(),
            ports={"i_a": migen.Signal()},
            core_params={"i_b": migen.Signal()},
        )

    with pytest.raises(ValueError):
        Amaranth2VConverter(
            platform=_DummyPlatform(),
            domains=["sys"],
            clock_domains=["usb"],
        )


def test_parse_port_keyword_valid():
    assert Amaranth2VConverter._parse_port_keyword("i_rx_data") == ("i", ["rx", "data"])
    assert Amaranth2VConverter._parse_port_keyword("io_pad") == ("io", ["pad"])
    assert Amaranth2VConverter._parse_port_keyword("o__bus_pullup_o") == ("o", ["_bus", "pullup", "o"])
    assert Amaranth2VConverter._parse_port_keyword("i_cd_sys_clk") == ("i", ["cd", "sys", "clk"])


@pytest.mark.parametrize("kw", [
    "foo",
    "x_sig",
    "i_",
    "i___sig",
    "o_sig_",
    "i_1bad",
])
def test_parse_port_keyword_invalid(kw):
    with pytest.raises(ValueError):
        Amaranth2VConverter._parse_port_keyword(kw)


def test_unresolved_signal_error_contains_diagnostics():
    dut = _converter(core_params={"i_missing_signal": migen.Signal()})

    with pytest.raises(ValueError) as e:
        dut.connect_wrapper()

    msg = str(e.value)
    assert "Cannot resolve 'i_missing_signal'" in msg
    assert "Parsed direction: i" in msg
    assert "Parsed path: missing/signal" in msg
    assert "Tried wrapper attribute: 'missing'" in msg
    assert "Available clock domains:" in msg


def test_duplicate_resolution_is_rejected():
    class _AliasTop(amaranth.Elaboratable):
        def __init__(self):
            self.sig = amaranth.Signal()
            self.alias = self.sig

        def elaborate(self, _platform):
            return amaranth.Module()

    top = _AliasTop()
    dut = _converter(
        module=top,
        core_params={
            "i_sig": migen.Signal(),
            "i_alias": migen.Signal(),
        }
    )

    with pytest.raises(ValueError) as e:
        dut.connect_wrapper()

    assert "Ambiguous ports" in str(e.value)
    assert "'i_sig'" in str(e.value)
    assert "'i_alias'" in str(e.value)


def test_get_instance_accepts_io_direction():
    dut = _converter()
    am_sig = amaranth.Signal()
    mg_sig = migen.Signal()
    dut.conn_list = [("io", am_sig, mg_sig)]
    dut.amaranth_name_map = amaranth.hdl._ast.SignalDict()
    dut.amaranth_name_map[am_sig] = ("pad", "io")

    inst = dut.get_instance()
    assert len(inst.items) == 1
    assert isinstance(inst.items[0], migen.fhdl.specials.Instance.InOut)
    assert inst.items[0].name == "pad"
    assert inst.items[0].expr is mg_sig
