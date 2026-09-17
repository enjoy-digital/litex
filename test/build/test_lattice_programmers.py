#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

from unittest.mock import patch

from litex.build.lattice.programmer import (
    EcpDapProgrammer,
    EcpprogProgrammer,
    IceStormProgrammer,
)


def test_icestorm_programmer_commands():
    programmer = IceStormProgrammer()
    with patch.object(programmer, "call") as call:
        programmer.load_bitstream("/tmp/top.bit")
        programmer.flash(0x20000, "/tmp/top.bit")

    assert call.call_args_list[0].args[0] == ["iceprog", "-S", "/tmp/top.bit"]
    assert call.call_args_list[1].args[0] == ["iceprog", "-o", str(0x20000), "/tmp/top.bit"]


def test_ecpdap_programmer_commands():
    programmer = EcpDapProgrammer(frequency=12_000_000)
    with patch.object(programmer, "call") as call:
        programmer.load_bitstream("/tmp/top.bit")
        programmer.flash(0x40000, "/tmp/top.bit")

    assert call.call_args_list[0].args[0] == [
        "ecpdap", "program", "--freq", "12000000", "/tmp/top.bit"
    ]
    assert call.call_args_list[1].args[0] == [
        "ecpdap", "flash", "write", "--freq", "12000000",
        "--offset", str(0x40000), "/tmp/top.bit"
    ]


def test_ecpprog_programmer_commands():
    programmer = EcpprogProgrammer()
    with patch.object(programmer, "call") as call:
        programmer.load_bitstream("/tmp/top.bit")
        programmer.flash(0, "/tmp/top.bit")

    assert call.call_args_list[0].args[0] == ["ecpprog", "-S", "/tmp/top.bit"]
    assert call.call_args_list[1].args[0] == ["ecpprog", "-o", "0", "/tmp/top.bit"]
