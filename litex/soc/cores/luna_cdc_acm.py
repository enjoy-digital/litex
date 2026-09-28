#
# Copyright (c) 2025 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
#
# SPDX-License-Identifier: BSD-2-Clause
"""LiteX/LUNA USB CDC-ACM bridge.

This module wraps LUNA's :class:`USBSerialDevice` and exposes it as LiteX stream
endpoints in the ``sys`` domain:
- ``sink``   : TX bytes from LiteX to USB host.
- ``source`` : RX bytes from USB host to LiteX.

Data is transferred through CDC shims between ``sys`` and:
- ``usb_12`` for raw USB full-speed D+/D- pads.
- ``usb`` for ULPI pads or a UTMI PHY.

Clock requirements depend on the selected bus type:
- Raw USB full-speed mode:
  - ``usb_12`` must run at 12 MHz (USB full-speed protocol clock).
  - ``usb_48`` must run at 48 MHz (USB PHY I/O clock).
  - ``usb_48`` should be generated from the same PLL/source as ``usb_12``
    (exact 4x relationship) to avoid long-term drift between protocol and I/O.
- ULPI mode:
  - external ``usb_12``/``usb_48`` domains are not required.
  - ULPI clock direction depends on PHY integration:
    - ``clk``: PHY drives the clock, core consumes it directly.
    - ``clk_n``: PHY drives the inverted form of the same clock, and the core
      internally uses ``~clk_n`` as the ULPI clock input.
    - ``clk_o``: core drives the clock, PHY consumes it.
  - This core creates the ``usb`` clock domain around LUNA USB IP.
  - With ``clk`` or ``clk_n``, LUNA drives ``ClockSignal("usb")`` from the
    ULPI PHY clock.
  - With ``clk_o``, LUNA consumes ``ClockSignal("usb")``, which must be driven by the SoC.
- UTMI mode (8-bit, 60 MHz UTMI PHY, ex: a soft USB 2.0 PHY):
  - ``usb`` must be provided by the SoC: UTMI clock (60 MHz) and reset.
  - the device runs at High-Speed (Full-Speed fallback), 512-byte bulk packets.
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

from luna.gateware.interface.utmi import UTMIInterface

# UTMI Layout --------------------------------------------------------------------------------------

# UTMI signals (LUNA names), direction from the PHY: "i" (PHY -> LUNA) / "o" (LUNA -> PHY).
utmi_layout = [
    ("rx_data",     8, "i"),
    ("rx_valid",    1, "i"),
    ("rx_active",   1, "i"),
    ("rx_error",    1, "i"),
    ("line_state",  2, "i"),
    ("tx_data",     8, "o"),
    ("tx_valid",    1, "o"),
    ("tx_ready",    1, "i"),
    ("op_mode",     2, "o"),
    ("xcvr_select", 2, "o"),
    ("term_select", 1, "o"),
]

# LUNA High-Speed UTMI Serial Device ---------------------------------------------------------------

class _USBSerialDeviceUTMI(luna.full_devices.USBSerialDevice):
    """LUNA USBSerialDevice on a UTMI PHY: High-Speed capable (LUNA uses a raw UTMI bus at Full-Speed
    only, with a 12 MHz data clock)."""
    def elaborate(self, platform):
        m   = super().elaborate(platform)
        usb = m.submodules.usb
        usb.always_fs  = False
        usb.data_clock = 60e6
        return m

# LunaCDCACM ---------------------------------------------------------------------------------------

class LunaCDCACM(LiteXModule):
    """USB CDC-ACM serial function for LiteX designs.

    Parameters:
        platform: LiteX platform used by :class:`Amaranth2VConverter`.
        pads: USB bus pads. Supported variants:
            - Raw USB full-speed: ``d_p``, ``d_n``, ``pullup``.
            - ULPI: ``data``, ``stp``, ``nxt``, ``dir`` and clock
              (``clk`` input, ``clk_n`` inverted input, or ``clk_o`` output),
              with optional ``rst``/``rst_n``.
            - UTMI: UTMI PHY interface with the ``utmi_layout`` signals (``rx_data``,
              ``rx_active``, ``tx_ready``, ...).
        vid: USB vendor ID (default: ``0x1209``).
        pid: USB product ID (default: ``0x0001``).

    Exposed attributes:
        sink: LiteX stream endpoint carrying bytes to USB (TX path).
        source: LiteX stream endpoint carrying bytes from USB (RX path).
        connect: Control signal that enables the CDC ACM connection.

    Clock domains expected in the SoC:
        - ``sys``    : LiteX logic side.
        - Raw USB full-speed mode only:
          - ``usb_12`` : USB protocol domain, required at 12 MHz.
          - ``usb_48`` : USB I/O domain, required at 48 MHz.
        - ULPI mode:
          - no externally provided ``usb_12``/``usb_48`` domains are required.
          - this core creates ``usb`` clock domain for LUNA.
          - with ``clk``: LUNA drives ``usb`` from the direct ULPI PHY clock.
          - with ``clk_n``: LUNA drives ``usb`` from the inverted ULPI PHY
            clock input by internally using ``~clk_n``.
          - with ``clk_o``: LUNA consumes ``usb`` clock provided by the SoC.
        - UTMI mode: ``usb`` (60 MHz UTMI clock, reset) provided by the SoC.

    Notes:
        In raw USB full-speed mode, ``usb_12`` and ``usb_48`` are consumed by
        the LUNA core. Keep them frequency-locked (``usb_48 = 4 * usb_12``),
        ideally from a single PLL/MMCM, so packet timing remains stable.

        In ULPI input-clock mode, ``clk`` and ``clk_n`` describe the same
        external clock with opposite polarity:
        - use ``clk`` when the pad already carries the non-inverted ULPI clock;
        - use ``clk_n`` when the available pad is the inverted clock
        - do not provide both at the same time.
    """
    def __init__(self, platform, pads=None, vid=0x1209, pid=0x0001):
        self.source  = source = stream.Endpoint([("data", 8)])
        self.sink    = sink   = stream.Endpoint([("data", 8)])

        self.connect = Signal()

        assert pads is not None
        assert hasattr(pads, "d_p") or hasattr(pads, "data") or hasattr(pads, "rx_active")

        # # #

        self.platform    = platform
        self.core_params = {}
        self.cd_list     = ["usb"]
        is_ulpi          = hasattr(pads, "data")      # ULPI.
        is_utmi          = hasattr(pads, "rx_active") # UTMI.
        cd_sync          = {True: "usb", False: "usb_12"}[is_ulpi or is_utmi]

        # CDC ACM clock domain converter -----------------------------------------------------------
        self.tx_cdc = tx_cdc = stream.ClockDomainCrossing([("data", 8)],
            cd_from = "sys",
            cd_to   = cd_sync,
        )
        self.rx_cdc = rx_cdc = stream.ClockDomainCrossing([("data", 8)],
            cd_from = cd_sync,
            cd_to   = "sys",
        )
        self.comb += [
            sink.connect(tx_cdc.sink),
            rx_cdc.source.connect(source)
        ]
        sink, source = tx_cdc.source, rx_cdc.sink

        # Clk/Rst ----------------------------------------------------------------------------------

        self.core_params.update({
            "i_sync_clk" : ClockSignal(cd_sync),
            "i_sync_rst" : ResetSignal(cd_sync),
        })

        if is_ulpi:
            is_clk_in   = hasattr(pads, 'clk') or hasattr(pads, 'clk_n')
            ulpi_rst    = Signal()
            self.cd_usb = ClockDomain("usb")

            # Power on reset
            self.cd_usb_por = ClockDomain()
            por_count       = Signal(16, reset=(2**16-1) // 4)
            por_done        = Signal()
            self.comb += [
                self.cd_usb_por.clk.eq(ClockSignal("usb")),
                self.cd_usb_por.rst.eq(ResetSignal("sys")),
                por_done.eq(por_count == 0)
            ]
            self.sync.usb_por += If(~por_done, por_count.eq(por_count - 1))
            self.comb += ResetSignal("usb").eq(~por_done)

            if is_clk_in:
                pads_clk = Signal(reset_less=True)

                if hasattr(pads, 'clk'):
                    self.comb += pads_clk.eq(pads.clk)
                else:
                    self.comb += pads_clk.eq(~pads.clk_n)
                self.core_params.update({
                    "i__bus_clk_i" : pads_clk,
                    "o_usb_clk"    : ClockSignal("usb"),
                })
                platform.add_period_constraint(pads_clk, 1e9/60e6)
            else:
                self.core_params.update({
                    "o__bus_clk_o" : pads.clk_o,
                    "i_usb_clk"    : ClockSignal("usb"),
                })

            self.core_params.update({
                "i_usb_rst"    : ResetSignal("usb"),
                "o__bus_rst_o" : ulpi_rst,
            })

            if hasattr(pads, 'rst'):
                self.comb += pads.rst.eq(ulpi_rst)
            elif hasattr(pads, 'rst_n'):
                self.comb += pads.rst_n.eq(~(ulpi_rst))
        elif is_utmi:
            self.core_params.update({
                "i_usb_clk" : ClockSignal("usb"),
                "i_usb_rst" : ResetSignal("usb"),
            })
        else:
            self.core_params.update({
                "i_usb_clk"    : ClockSignal("usb_12"),
                "i_usb_io_clk" : ClockSignal("usb_48"),
                "i_usb_io_rst" : ResetSignal("usb_48"),
            })
            self.cd_list.append("usb_io")

        # Signals ----------------------------------------------------------------------------------

        if is_ulpi:
            ulpi_data = TSTriple(8)
            self.specials += ulpi_data.get_tristate(pads.data)

            bus = aRecord([
                ('data', [('i', 8, DIR_FANIN), ('o', 8, DIR_FANOUT), ('oe', 1, DIR_FANOUT)]),
                ('clk',  [('i', 1, DIR_FANIN)] if is_clk_in else [('o', 1, DIR_FANOUT)]),
                ('stp',  [('o', 1, DIR_FANOUT)]),
                ('nxt',  [('i', 1, DIR_FANIN)]),
                ('dir',  [('i', 1, DIR_FANIN)]),
                ('rst',  [('o', 1, DIR_FANOUT)]),
            ])

            self.core_params.update({
                "i__bus_data_i"  : ulpi_data.i,
                "o__bus_data_o"  : ulpi_data.o,
                "o__bus_data_oe" : ulpi_data.oe,
                "o__bus_stp_o"   : pads.stp,
                "i__bus_nxt_i"   : pads.nxt,
                "i__bus_dir_i"   : pads.dir,
            })
        elif is_utmi:
            bus = UTMIInterface()
            for name, _, direction in utmi_layout:
                self.core_params[f"{direction}__bus_{name}"] = getattr(pads, name)
        else:
            ulpi_d_p = TSTriple()
            ulpi_d_n = TSTriple()
            self.specials += [
                ulpi_d_p.get_tristate(pads.d_p),
                ulpi_d_n.get_tristate(pads.d_n),
            ]

            bus = aRecord([
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

        if is_utmi:
            self.usb = usb = _USBSerialDeviceUTMI(bus=bus,
                idVendor        = vid,
                idProduct       = pid,
                max_packet_size = 512,
            )
        else:
            self.usb = usb = luna.full_devices.USBSerialDevice(bus=bus,
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
            ports         = self.core_params,
            domains       = self.cd_list,
            output_dir    = None,
        )
