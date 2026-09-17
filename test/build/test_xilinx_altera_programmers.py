#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

from unittest.mock import patch

from litex.build.altera.programmer import USBBlaster
from litex.build.xilinx.programmer import Adept, FpgaProg, XC3SProg


def test_usbblaster_programmer_command():
    programmer = USBBlaster(cable_name="USB-Blaster", device_id=2)
    with patch.object(programmer, "call") as call:
        programmer.load_bitstream("/tmp/top.sof", cable_suffix="-1")

    assert call.call_args_list[0].args[0] == [
        "quartus_pgm", "-m", "jtag", "-c", "USB-Blaster-1",
        "-o", "p;/tmp/top.sof@2",
    ]


def test_xc3sprog_programmer_load_command():
    programmer = XC3SProg(cable="xpc", position=1)
    with patch.object(programmer, "call") as call:
        programmer.load_bitstream("/tmp/top.bit")

    assert call.call_args_list[0].args[0] == [
        "xc3sprog", "-v", "-c", "xpc", "-p", "1", "/tmp/top.bit"
    ]


def test_xc3sprog_programmer_flash_command():
    programmer = XC3SProg(cable="xpc", position=1, flash_proxy_basename="bscan_spi_xc6s")
    with patch.object(programmer, "find_flash_proxy", return_value="bscan_spi_xc6s.bit"), \
         patch.object(programmer, "call") as call:
        programmer.flash(0x40000, "/tmp/top.bit")

    assert call.call_args_list[0].args[0] == [
        "xc3sprog", "-v", "-c", "xpc", "-p", "1",
        "-Ibscan_spi_xc6s.bit", "/tmp/top.bit:w:0x40000:BIN"
    ]


def test_fpgaprog_programmer_load_and_flash_commands():
    programmer = FpgaProg(flash_proxy_basename="bscan_spi_xc6s")
    with patch.object(programmer, "find_flash_proxy", return_value="bscan_spi_xc6s.bit"), \
         patch.object(programmer, "call") as call:
        programmer.load_bitstream("/tmp/top.bit")
        programmer.flash(0, "/tmp/top.bit")

    assert call.call_args_list[0].args[0] == ["fpgaprog", "-v", "-f", "/tmp/top.bit"]
    assert call.call_args_list[1].args[0] == [
        "fpgaprog", "-v", "-sa", "-r", "-b", "bscan_spi_xc6s.bit", "-f", "/tmp/top.bit"
    ]


def test_adept_programmer_load_command():
    programmer = Adept(board="arty", index=0)
    with patch.object(programmer, "call") as call:
        programmer.load_bitstream("/tmp/top.bit")

    assert call.call_args_list[0].args[0] == [
        "djtgcfg", "--verbose", "prog", "-d", "arty", "-i", "0", "-f", "/tmp/top.bit"
    ]
