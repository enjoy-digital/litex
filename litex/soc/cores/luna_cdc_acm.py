#
# Copyright (c) 2025 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
#
# SPDX-License-Identifier: BSD-2-Clause
"""LiteX/LUNA USB CDC-ACM bridge.

This module wraps LUNA's :class:`USBSerialDevice` and exposes it as LiteX stream
endpoints in the ``sys`` domain:
- ``sink``   : TX bytes from LiteX to USB host.
- ``source`` : RX bytes from USB host to LiteX.

Data is transferred through CDC shims between ``sys`` and ``usb_12`` domains,
while USB I/O runs from ``usb_48``.

Clock requirements:
- ``usb_12`` must run at 12 MHz (USB full-speed protocol clock).
- ``usb_48`` must run at 48 MHz (USB PHY I/O clock).
- ``usb_48`` should be generated from the same PLL/source as ``usb_12``
  (exact 4x relationship) to avoid long-term drift between protocol and I/O.
"""

import os
import subprocess

import migen

from litex.build.io import SDRTristate

from litex.build.amaranth2v_converter import Amaranth2VConverter

from litex.gen import *

from litex.soc.interconnect import stream

from amaranth         import Record as aRecord
from amaranth.hdl.rec import DIR_FANIN, DIR_FANOUT

import luna.full_devices

# LunaCDCACM ---------------------------------------------------------------------------------------

class LunaCDCACM(LiteXModule):
    """USB CDC-ACM serial function for LiteX designs.

    Parameters:
        platform: LiteX platform used by :class:`Amaranth2VConverter`.
        pads: USB full-speed pads object with ``d_p``, ``d_n`` and ``pullup``.
        vid: USB vendor ID (default: ``0x1209``).
        pid: USB product ID (default: ``0x0001``).

    Exposed attributes:
        sink: LiteX stream endpoint carrying bytes to USB (TX path).
        source: LiteX stream endpoint carrying bytes from USB (RX path).
        connect: Control signal that enables the CDC ACM connection.

    Clock domains expected in the SoC:
        - ``sys``    : LiteX logic side.
        - ``usb_12`` : USB protocol domain, required at 12 MHz.
        - ``usb_48`` : USB I/O domain, required at 48 MHz.

    Notes:
        ``usb_12`` and ``usb_48`` are both consumed by the LUNA core.
        Keep them frequency-locked (``usb_48 = 4 * usb_12``), ideally from a
        single PLL/MMCM, so packet timing remains stable.
    """
    def __init__(self, platform, pads=None, vid=0x1209, pid=0x0001):
        self.source  = source = stream.Endpoint([("data", 8)])
        self.sink    = sink   = stream.Endpoint([("data", 8)])

        self.connect = Signal()

        assert pads is not None
        assert hasattr(pads, "d_p")

        # # #

        self.platform    = platform
        self.core_params = {}
        self.cd_list     = ["usb", "usb_io"]

        # CDC ACM clock domain converter -----------------------------------------------------------
        self.tx_cdc = tx_cdc = stream.ClockDomainCrossing([("data", 8)],
            cd_from = "sys",
            cd_to   = "usb_12",
        )
        self.rx_cdc = rx_cdc = stream.ClockDomainCrossing([("data", 8)],
            cd_from = "usb_12",
            cd_to   = "sys",
        )
        self.comb += [
            sink.connect(tx_cdc.sink),
            rx_cdc.source.connect(source)
        ]
        sink, source = tx_cdc.source, rx_cdc.sink

        # Clk/Rst ----------------------------------------------------------------------------------

        self.core_params.update({
            "i_sync_clk"   : ClockSignal("usb_12"),
            "i_sync_rst"   : ResetSignal("usb_12"),
            "i_usb_clk"    : ClockSignal("usb_12"),
            "i_usb_io_clk" : ClockSignal("usb_48"),
            "i_usb_io_rst" : ResetSignal("usb_48"),
        })

        # Signals ----------------------------------------------------------------------------------

        ulpi_d_p = TSTriple()
        ulpi_d_n = TSTriple()
        self.specials += [
            ulpi_d_p.get_tristate(pads.d_p),
            ulpi_d_n.get_tristate(pads.d_n),
        ]

        ulpi = aRecord([
            ('d_p',    [('i', 1, DIR_FANIN), ('o', 1, DIR_FANOUT), ('oe', 1, DIR_FANOUT)]),
            ('d_n',    [('i', 1, DIR_FANIN), ('o', 1, DIR_FANOUT), ('oe', 1, DIR_FANOUT)]),
            ("pullup", [('o', 1, DIR_FANOUT)]),
        ])

        self.core_params.update({
            "i__bus_d_p_i"    : ulpi_d_p.i,
            "o__bus_d_p_o"    : ulpi_d_p.o,
            "o__bus_d_p_oe"   : ulpi_d_p.oe,
            "i__bus_d_n_i"    : ulpi_d_n.i,
            "o__bus_d_n_o"    : ulpi_d_n.o,
            "o__bus_d_n_oe"   : ulpi_d_n.oe,
            "o__bus_pullup_o" : pads.pullup,
        })

        # Connections ------------------------------------------------------------------------------

        self.core_params.update({
            # Controls.
            # ---------
            "i_connect"    : self.connect,

            # Source.
            # -------
            "o_rx_valid"   : source.valid,
            "i_rx_ready"   : source.ready,
            "o_rx_last"    : source.last,
            "o_rx_first"   : source.first,
            "o_rx_payload" : source.data,

            # Sink.
            # -----
            "i_tx_valid"   : sink.valid,
            "o_tx_ready"   : sink.ready,
            "i_tx_last"    : sink.valid,
            "i_tx_first"   : sink.valid,
            "i_tx_payload" : sink.data,
        })

        # LUNA USB CDC-ACM -------------------------------------------------------------------------

        self.usb = usb = luna.full_devices.USBSerialDevice(bus=ulpi,
            idVendor  = vid,
            idProduct = pid,
        )

    def do_finalize(self):
        # Check packages versions
        # luna-usb with version 0.2.3 (20260220: latest commit/release)
        # amaranth with version 0.5.8 (compatibily issue for luna with main branch)
        required_packages = {
            "luna-usb" : "0.2.3",
            "amaranth" : "0.5.8",
        }

        package_error = False
        for k, v in required_packages.items():
            error = False
            # Get pip3 informations
            result = subprocess.run(f"pip3 show {k}", shell=True, capture_output=True, text=True)
            if result.returncode == 1:
                print(f"Error: package {k} not installed")
                error = True
            if not error:
                res     = result.stdout.split("\n")
                # Extract "Version: xxx" line and get the value
                version = [l for l in res if l.startswith('Version')][0].split(": ")[1]
                # Check match
                if not version.startswith(v):
                    print(f"Error: {k} installed with wrong version: expected {v} seen {version}")
                    error = True
            # When error: provides required command to install the package.
            if error:
                print(f"Please install package {k} with command:")
                print(f"    pip3 install --user {k}=={v}")
                package_error = True

        # Missing package or wrong version: stop.
        if package_error:
            exit(1)

        # Amaranth Converter -----------------------------------------------------------------------
        self.converter = Amaranth2VConverter(self.platform,
            name          = "usb_cdc_acm",
            module        = self.usb,
            core_params   = self.core_params,
            clock_domains = self.cd_list,
            output_dir    = None,
        )
