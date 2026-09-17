#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import pytest

from litex.build.efinix.programmer import EfinixProgrammer


def _programmer(family=None):
    programmer = object.__new__(EfinixProgrammer)
    programmer.efinity_path = "/opt/efinity"
    programmer.family = family
    return programmer


def test_load_bitstream_command():
    programmer = _programmer()

    assert programmer._load_bitstream_command("/tmp/top.bit") == [
        "/opt/efinity/bin/python3",
        "/opt/efinity/pgm/bin/efx_pgm/ftdi_program.py",
        "/tmp/top.bit",
        "-m", "jtag",
    ]
    assert programmer._load_bitstream_command("/tmp/top.bit", "extra")[-1] == "extra"


def test_flash_command():
    programmer = _programmer()

    assert programmer._flash_command(0x40000, "/tmp/top.hex") == [
        "/opt/efinity/bin/python3",
        "/opt/efinity/pgm/bin/efx_pgm/ftdi_program.py",
        "/tmp/top.hex",
        "-m", "jtag_bridge",
        "--address", hex(0x40000),
    ]


def test_bridge_image_path_titanium_auto_name():
    programmer = _programmer(family="Titanium")

    assert programmer._bridge_image_path(None, 0x1234).endswith("titanium/u00001234.bit")


def test_bridge_image_path_topaz_and_trion():
    assert _programmer(family="Topaz")._bridge_image_path("bridge.bit", None).endswith("topaz/bridge.bit")
    assert _programmer(family="Trion")._bridge_image_path("bridge.bit", None).endswith("trion/bridge.bit")


def test_bridge_image_path_trion_requires_bridge_name():
    with pytest.raises(ValueError, match="Trion devices require a bridge image name"):
        _programmer(family="Trion")._bridge_image_path(None, None)


def test_bridge_image_path_rejects_unknown_family():
    with pytest.raises(ValueError, match="Unknown Efinix family"):
        _programmer(family="Unknown")._bridge_image_path("bridge.bit", None)
