#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Pmod modules, described once as Extensions and usable on any board exposing Pmod connectors.

Canonical Pmod connector: 8 entries, index 0-3 = physical pins 1-4 (top row), index 4-7 = physical
pins 7-10 (bottom row). GND/VCC pins are not part of the connector. Boards declaring their Pmods
differently should expose a canonical alias connector.

Usage:

    from litex.build.pmod import PmodSDCard
    platform.add_extension(PmodSDCard("pmodd"))
    sdcard_pads = platform.request("sdcard")
"""

from litex.build.generic_platform import Pins, Subsignal
from litex.build.extension import Extension

# Pmod Extension -----------------------------------------------------------------------------------

class PmodExtension(Extension):
    slots          = {"pmod": None}
    connector_type = "pmod"

# GPIO ---------------------------------------------------------------------------------------------

class PmodGPIO(PmodExtension):
    """Raw 8-bit GPIO resource, named after the host connector (ex: request("pmoda"))."""
    def define_io(self, platform):
        return [
            (self.bindings["pmod"], 0, Pins(" ".join(f"pmod:{i}" for i in range(8))), *self.iostandard(platform)),
        ]

# USB-UART -----------------------------------------------------------------------------------------

class PmodUSBUART(PmodExtension):
    """Digilent PmodUSBUART: https://digilent.com/reference/pmod/pmodusbuart/start"""
    def define_io(self, platform):
        return [
            ("usb_uart", 0,
                Subsignal("tx", Pins("pmod:1")),
                Subsignal("rx", Pins("pmod:2")),
                *self.iostandard(platform),
            ),
        ]

# SDCard -------------------------------------------------------------------------------------------

class PmodSDCard(PmodExtension):
    """Digilent PmodMicroSD (and compatible, ex antmicro arty-expansion-board).

    https://digilent.com/reference/pmod/pmodmicrosd/start
    """
    def define_io(self, platform):
        pullup    = self.pullup(platform)
        slew_fast = self.slew_fast(platform)
        return [
            ("spisdcard", 0,
                Subsignal("clk",  Pins("pmod:3")),
                Subsignal("mosi", Pins("pmod:1"), *pullup),
                Subsignal("cs_n", Pins("pmod:0"), *pullup),
                Subsignal("miso", Pins("pmod:2"), *pullup),
                *slew_fast,
                *self.iostandard(platform),
            ),
            ("sdcard", 0,
                Subsignal("data", Pins("pmod:2 pmod:4 pmod:5 pmod:0"), *pullup),
                Subsignal("cmd",  Pins("pmod:1"), *pullup),
                Subsignal("clk",  Pins("pmod:3")),
                Subsignal("cd",   Pins("pmod:6")),
                *slew_fast,
                *self.iostandard(platform),
            ),
        ]

class PmodNumatoSDCard(PmodExtension):
    """Numato Micro SD expansion module (no card detect).

    https://numato.com/product/micro-sd-expansion-module/
    """
    def define_io(self, platform):
        pullup    = self.pullup(platform)
        slew_fast = self.slew_fast(platform)
        return [
            ("spisdcard", 0,
                Subsignal("clk",  Pins("pmod:5")),
                Subsignal("mosi", Pins("pmod:1"), *pullup),
                Subsignal("cs_n", Pins("pmod:4"), *pullup),
                Subsignal("miso", Pins("pmod:2"), *pullup),
                *slew_fast,
                *self.iostandard(platform),
            ),
            ("sdcard", 0,
                Subsignal("data", Pins("pmod:2 pmod:6 pmod:0 pmod:4"), *pullup),
                Subsignal("cmd",  Pins("pmod:1"), *pullup),
                Subsignal("clk",  Pins("pmod:5")),
                *slew_fast,
                *self.iostandard(platform),
            ),
        ]

# Audio --------------------------------------------------------------------------------------------

class PmodI2S2(PmodExtension):
    """Digilent PmodI2S2: https://digilent.com/reference/pmod/pmodi2s2/start"""
    def define_io(self, platform):
        iostd = self.iostandard(platform)
        return [
            ("i2s_rx_mclk", 0, Pins("pmod:4"), *iostd),
            ("i2s_rx", 0,
                Subsignal("clk",  Pins("pmod:6")),
                Subsignal("sync", Pins("pmod:5")),
                Subsignal("rx",   Pins("pmod:7")),
                *iostd,
            ),
            ("i2s_tx_mclk", 0, Pins("pmod:0"), *iostd),
            ("i2s_tx", 0,
                Subsignal("clk",  Pins("pmod:2")),
                Subsignal("sync", Pins("pmod:1")),
                Subsignal("tx",   Pins("pmod:3")),
                *iostd,
            ),
        ]

# Buses --------------------------------------------------------------------------------------------

class PmodCAN(PmodExtension):
    """SN65HVD230 based CAN transceiver: https://www.waveshare.com/sn65hvd230-can-board.htm"""
    def define_io(self, platform):
        return [
            ("can", 0,
                Subsignal("tx", Pins("pmod:2")),
                Subsignal("rx", Pins("pmod:3")),
                *self.iostandard(platform),
            ),
        ]

class PmodI2C(PmodExtension):
    """Generic I2C on Pmod pins 1 (SDA) and 2 (SCL)."""
    def define_io(self, platform):
        return [
            ("i2c", 0,
                Subsignal("sda", Pins("pmod:0")),
                Subsignal("scl", Pins("pmod:1")),
                *self.iostandard(platform),
            ),
        ]

class PmodJTAG(PmodExtension):
    """Generic JTAG on Pmod pins 1-4 (TCK, TDI, TDO, TMS)."""
    def define_io(self, platform):
        return [
            ("jtag", 0,
                Subsignal("tck", Pins("pmod:0")),
                Subsignal("tdi", Pins("pmod:1")),
                Subsignal("tdo", Pins("pmod:2")),
                Subsignal("tms", Pins("pmod:3")),
                *self.iostandard(platform),
            ),
        ]

class PmodPS2(PmodExtension):
    """PS/2 keyboard on Pmod pins 1 (data) and 3 (clk)."""
    def define_io(self, platform):
        return [
            ("ps2kbd", 0, Pins("pmod:0 pmod:2"), *self.iostandard(platform)), # data, clk.
        ]

# Ethernet -----------------------------------------------------------------------------------------

class PmodLAN8720(PmodExtension):
    """LAN8720 RMII PHY board used as a Pmod.

    To be used as a Pmod, MDIO should be disconnected and TX1 connected to Pmod pin 10.
    """
    def define_io(self, platform):
        iostd = self.iostandard(platform)
        return [
            ("eth_rmii_clocks", 0,
                Subsignal("ref_clk", Pins("pmod:6")),
                *iostd,
            ),
            ("eth_rmii", 0,
                Subsignal("rx_data", Pins("pmod:5 pmod:1")),
                Subsignal("crs_dv",  Pins("pmod:2")),
                Subsignal("tx_en",   Pins("pmod:4")),
                Subsignal("tx_data", Pins("pmod:0 pmod:7")),
                *iostd,
            ),
        ]

# USB ----------------------------------------------------------------------------------------------

class PmodUSBHostDual(PmodExtension):
    """Machdyne USB host dual socket Pmod: https://github.com/machdyne/usb_host_dual_socket_pmod

    usb_host:0 is the top socket (USB1), usb_host:1 the bottom socket (USB2).
    """
    def define_io(self, platform):
        iostd = self.iostandard(platform)
        return [
            ("usb_host", 0,
                Subsignal("dp", Pins("pmod:2")),
                Subsignal("dm", Pins("pmod:3")),
                *iostd,
            ),
            ("usb_host", 1,
                Subsignal("dp", Pins("pmod:0")),
                Subsignal("dm", Pins("pmod:1")),
                *iostd,
            ),
        ]

# Video --------------------------------------------------------------------------------------------

class PmodDVI(Extension):
    """1BitSquared DVI Pmod (dual Pmod): https://1bitsquared.com/products/pmod-digital-video-interface"""
    slots          = {"a": None, "b": None}
    connector_type = "pmod"

    def define_io(self, platform):
        return [
            ("dvi", 0,
                Subsignal("clk",   Pins("b:1")),
                Subsignal("de",    Pins("b:6")),
                Subsignal("hsync", Pins("b:3")),
                Subsignal("vsync", Pins("b:7")),
                Subsignal("r",     Pins("a:5 a:1 a:4 a:0")),
                Subsignal("g",     Pins("a:7 a:3 a:6 a:2")),
                Subsignal("b",     Pins("b:2 b:5 b:4 b:0")),
                *self.iostandard(platform),
            ),
        ]

# Registry -----------------------------------------------------------------------------------------

pmods = {
    "gpio"          : PmodGPIO,
    "usb_uart"      : PmodUSBUART,
    "sdcard"        : PmodSDCard,
    "numato_sdcard" : PmodNumatoSDCard,
    "i2s"           : PmodI2S2,
    "can"           : PmodCAN,
    "i2c"           : PmodI2C,
    "jtag"          : PmodJTAG,
    "ps2"           : PmodPS2,
    "lan8720"       : PmodLAN8720,
    "usb_host_dual" : PmodUSBHostDual,
}

# Command line -------------------------------------------------------------------------------------

# Pmods that can be plugged from the command line with the cores attached by add_pmods().
_cli_pmods = ["gpio", "sdcard", "numato_sdcard", "i2c", "can"]

def _pmod_arg(arg):
    import argparse
    try:
        parse_pmod_args([arg])
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))
    return arg

def add_pmod_args(parser):
    """Add a repeatable --pmod CONNECTOR=MODULE argument to a target's parser."""
    group = parser.target_group if hasattr(parser, "target_group") else parser
    group.add_argument("--pmod", action="append", default=[], metavar="CONNECTOR=MODULE", type=_pmod_arg,
        help=f"Plug a Pmod module on a connector (ex: pmoda=gpio). Modules: {', '.join(_cli_pmods)}.")

def parse_pmod_args(pmod_args):
    """Parse --pmod arguments into a list of (connector, module)."""
    r = []
    for arg in pmod_args:
        if arg.count("=") != 1:
            raise ValueError(f"Invalid --pmod argument '{arg}', expected CONNECTOR=MODULE.")
        conn, module = arg.split("=")
        if module not in _cli_pmods:
            raise ValueError(f"Unsupported Pmod module '{module}', supported: {', '.join(_cli_pmods)}.")
        r.append((conn, module))
    return r

def add_pmods(soc, pmod_args):
    """Plug Pmods described by --pmod arguments and add the corresponding cores to the SoC.

    - gpio                 : GPIOTristate core (named <connector>_gpio).
    - sdcard/numato_sdcard : IOs only (taking precedence over board's ones), to be used with
                             --with-sdcard/--with-spi-sdcard.
    - i2c                  : I2CMaster core (named <connector>_i2c).
    - can                  : CTU-CAN-FD core (named <connector>_can).
    """
    platform = soc.platform
    numbers  = {}
    for conn, module in parse_pmod_args(pmod_args):
        number = numbers.get(module, 0)
        numbers[module] = number + 1
        if module in ["sdcard", "numato_sdcard"] and number:
            raise ValueError("Only one SDCard Pmod is supported.")
        # Prepend so that explicitly plugged Pmods take precedence over board's default resources.
        platform.add_extension(pmods[module](conn, number=number), prepend=True)
        if module == "gpio":
            from litex.soc.cores.gpio import GPIOTristate
            soc.add_module(name=f"{conn}_gpio", module=GPIOTristate(
                pads     = platform.request(conn),
                with_irq = soc.irq.enabled,
            ))
        if module == "i2c":
            from litex.soc.cores.bitbang import I2CMaster
            soc.add_module(name=f"{conn}_i2c", module=I2CMaster(platform.request("i2c", number)))
        if module == "can":
            from litex.soc.integration.soc import SoCRegion
            from litex.soc.cores.can.ctu_can_fd import CTUCANFD
            name = f"{conn}_can"
            soc.add_module(name=name, module=CTUCANFD(platform, platform.request("can", number)))
            soc.bus.add_slave(name, getattr(soc, name).bus, SoCRegion(size=0x10000, mode="rw", cached=False))
            if soc.irq.enabled:
                soc.irq.add(name, use_loc_if_exists=True)
