#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Pmod helper resources.

This is a compatibility subset of the newer LiteX Pmod extension helpers for
LiteX trees that do not yet provide litex.build.extension.
"""

from litex.build.generic_platform import Pins, Subsignal


class PmodExtension:
    connector_type = "pmod"

    def __init__(self, pmod, number=0, name=None):
        self.pmod   = pmod
        self.number = number
        self.name   = name

    def get_io(self, platform):
        return self.define_io(platform)

    def __iter__(self):
        return iter(self.get_io(None))

    def _pins(self, *indexes):
        return Pins(" ".join(f"{self.pmod}:{i}" for i in indexes))


class PmodGPIO(PmodExtension):
    """Raw 8-bit GPIO resource, named after the host connector."""

    def define_io(self, platform):
        return [
            (self.pmod, self.number, self._pins(*range(8))),
        ]


class PmodUART(PmodExtension):
    """Generic UART on a Pmod, defaulting to the Digilent UART Pmod pinout."""

    resource = "serial"

    def __init__(self, *args, tx=1, rx=2, **kwargs):
        self.tx = tx
        self.rx = rx
        PmodExtension.__init__(self, *args, **kwargs)

    def define_io(self, platform):
        return [
            (self.resource, self.number,
                Subsignal("tx", self._pins(self.tx)),
                Subsignal("rx", self._pins(self.rx)),
            ),
        ]


class PmodUSBUART(PmodUART):
    """Digilent PmodUSBUART."""

    resource = "usb_uart"


class PmodUSBHostDual(PmodExtension):
    """Dual USB host Pmod.

    usb_host:0 is the top socket, usb_host:1 the bottom socket. With
    bundled=True, both ports are described in a single resource for cores that
    expect multi-port pads.
    """

    resource = "usb_host"

    def __init__(self, *args, bundled=False, **kwargs):
        self.bundled = bundled
        PmodExtension.__init__(self, *args, **kwargs)

    def define_io(self, platform):
        resource = self.name or self.resource
        if self.bundled:
            return [
                (resource, self.number,
                    Subsignal("dp", self._pins(0, 2)),
                    Subsignal("dm", self._pins(1, 3)),
                ),
            ]
        return [
            (resource, self.number,
                Subsignal("dp", self._pins(2)),
                Subsignal("dm", self._pins(3)),
            ),
            (resource, self.number + 1,
                Subsignal("dp", self._pins(0)),
                Subsignal("dm", self._pins(1)),
            ),
        ]
