#!/usr/bin/env python3
#
# This file is part of LiteX.
#
# Copyright (c) 2021 Hans Baier <hansfbaier@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause
import os

import nmigen
from nmigen.back                import verilog
from luna.full_devices          import USBSerialDevice

from migen                      import Module, Signal, ClockSignal, Instance
from migen.fhdl.specials        import Tristate
from litex.soc.cores.uart       import UARTInterface

from litex.soc.interconnect.csr import AutoCSR

class _USBACMSerialDevice(nmigen.Elaboratable):
    """ nmigen device that acts as a 'USB-to-serial' interface """
    def __init__(self):
        self.ulpi = nmigen.Record([
            ("data",  [("i", 8), ("o", 8), ("oe", 8)]),
            ("clk",   [("i", 1)]),
            ("dir",   [("i", 1)]),
            ("nxt",   [("i", 1)]),
            ("stp",   [("o", 1)]),
            ("reset", [("o", 1)]),
        ], name="ulpi")

        # source
        self.source_valid   = nmigen.Signal()
        self.source_ready   = nmigen.Signal()
        self.source_first   = nmigen.Signal()
        self.source_last    = nmigen.Signal()
        self.source_payload = nmigen.Signal(8)

        # sink
        self.sink_valid     = nmigen.Signal()
        self.sink_ready     = nmigen.Signal()
        self.sink_first     = nmigen.Signal()
        self.sink_last      = nmigen.Signal()
        self.sink_payload   = nmigen.Signal(8)

    def elaborate(self, platform):
        m = nmigen.Module()

        m.domains.usb = nmigen.ClockDomain()

        m.submodules.usb_serial = usb_serial = \
                USBSerialDevice(bus=self.ulpi, idVendor=0x16d0, idProduct=0x0f3b)

        m.d.comb += [
            # wire the tx/rx streams outside
            usb_serial.tx.payload  .eq(self.sink_payload),
            usb_serial.tx.valid    .eq(self.sink_valid),
            usb_serial.tx.first    .eq(self.sink_first),
            usb_serial.tx.last     .eq(self.sink_last),
            self.sink_ready        .eq(usb_serial.tx.ready),

            self.source_payload    .eq(usb_serial.rx.payload),
            self.source_valid      .eq(usb_serial.rx.valid),
            self.source_first      .eq(usb_serial.rx.first),
            self.source_last       .eq(usb_serial.rx.last),
            usb_serial.rx.ready    .eq(self.source_ready),

            # ... and always connect by default.
            usb_serial.connect.eq(1)
        ]

        return m

class USBHighSpeedACMSerialPHY(Module, AutoCSR, UARTInterface):
    def __init__(self, platform):
        UARTInterface.__init__(self)
        self.platform = platform

        # we do a lookup request here, because the CRG
        # has to request the ULPI resource before
        # to get the clock input for the USB PLL
        self.ulpi = platform.lookup_request("ulpi", 0)
        ulpi_data_i  = Signal(8)
        ulpi_data_o  = Signal(8)
        ulpi_data_oe = Signal(8)
        ulpi_reset   = Signal()

        # enable the PHY, if it has a chip select
        if hasattr(self.ulpi, 'cs'):
            self.comb += self.ulpi.cs.eq(1)

        # wire up ULPI reset
        if hasattr(self.ulpi, 'reset_n'):
            self.comb += self.ulpi.reset_n.eq(~ulpi_reset)
        elif hasattr(self.ulpi, 'reset'):
            self.comb += self.ulpi.reset.eq(ulpi_reset)

        self.specials += Tristate(self.ulpi.data,
                                  i  = ulpi_data_i,
                                  o  = ulpi_data_o,
                                  oe = ulpi_data_oe)

        self._pads = dict(
            # ULPI
            i_ulpi__data__i       = ulpi_data_i,
            o_ulpi__data__o       = ulpi_data_o,
            o_ulpi__data__oe      = ulpi_data_oe,
            # this is the clock input of the USB core
            # coming from the USB PLL
            i_ulpi__clk__i        = ClockSignal("usb"),
            o_ulpi__stp__o        = self.ulpi.stp,
            i_ulpi__dir__i        = self.ulpi.dir,
            i_ulpi__nxt__i        = self.ulpi.nxt,
            o_ulpi__reset__o      = ulpi_reset,

            # source
            i_source_ready        = self.source.ready,
            o_source_valid        = self.source.valid,
            o_source_first        = self.source.first,
            o_source_last         = self.source.last,
            o_source_payload      = self.source.payload.data,

            # sink
            o_sink_ready          = self.sink.ready,
            i_sink_valid          = self.sink.valid,
            i_sink_first          = self.sink.first,
            i_sink_last           = self.sink.last,
            i_sink_payload        = self.sink.payload.data,
        )

    @staticmethod
    def elaborate(verilog_filename):
        usb_serial = _USBACMSerialDevice()
        v = verilog.convert(usb_serial,
                            name="usb_acm_serial",
                            strip_internal_attrs=True,
                            ports = list(usb_serial.ulpi._rhs_signals()) +
                                    [
                                        usb_serial.source_ready,
                                        usb_serial.source_valid,
                                        usb_serial.source_first,
                                        usb_serial.source_last,
                                        usb_serial.source_payload,
                                        usb_serial.sink_ready,
                                        usb_serial.sink_valid,
                                        usb_serial.sink_first,
                                        usb_serial.sink_last,
                                        usb_serial.sink_payload,
                                    ])

        with open(verilog_filename, 'w') as f:
            f.write(v)

    def do_finalize(self):
        verilog_filename = os.path.join(self.platform.output_dir, "gateware", "usb_acm_serial.v")
        self.elaborate(verilog_filename = verilog_filename)
        self.platform.add_source(verilog_filename)
        self.specials += Instance("usb_acm_serial", **self._pads)
