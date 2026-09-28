#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import re
import tempfile
import unittest

import pytest

pytest.importorskip("amaranth")
pytest.importorskip("luna")

from amaranth.sim import Passive

from luna.full_devices        import USBSerialDevice
from luna.gateware.test.usb2  import USBDeviceTest
from luna.gateware.test.utils import usb_domain_test_case
from luna.gateware.usb.usb2   import USBPacketID

from migen import *

from litex.build.generic_platform import GenericPlatform

from litex.soc.cores.luna_cdc_acm import LunaCDCACM, utmi_layout, _USBSerialDeviceUTMI

# Helpers ------------------------------------------------------------------------------------------

VID = 0x1209
PID = 0x5bf0

LINE_STATE_SE0 = 0b00
LINE_STATE_J   = 0b01

OP_MODE_CHIRP  = 0b10

DATA_ENDPOINT  = 4

class _UTMIDeviceTest(USBDeviceTest):
    FRAGMENT_UNDER_TEST = _USBSerialDeviceUTMI
    FRAGMENT_ARGUMENTS  = dict(idVendor=VID, idProduct=PID, max_packet_size=512)
    LINE_STATE          = LINE_STATE_J # Idle bus: no bus reset.

    def setUp(self):
        super().setUp()
        self.received = []
        self.sim.add_sync_process(self.line_state_process, domain="usb")
        self.sim.add_sync_process(self.rx_process,         domain="usb")

    def line_state_process(self):
        yield Passive()
        yield self.utmi.line_state.eq(self.LINE_STATE)

    def rx_process(self):
        yield Passive()
        yield self.dut.rx.ready.eq(1)
        while True:
            if (yield self.dut.rx.valid):
                self.received.append((yield self.dut.rx.payload))
            yield

    def chirp_cycle(self, cycles):
        """Cycle of the first High-Speed chirp (op_mode = chirp while transmitting), None if none."""
        for cycle in range(cycles):
            if (yield self.utmi.op_mode) == OP_MODE_CHIRP and (yield self.utmi.tx_valid):
                return cycle
            yield
        return None

# UTMI Device (LUNA simulation) --------------------------------------------------------------------

class TestLunaCDCACMUTMI(_UTMIDeviceTest):
    @usb_domain_test_case
    def test_device_descriptor(self):
        handshake, data = yield from self.get_descriptor(0x01, length=18)
        self.assertEqual(handshake, USBPacketID.ACK)
        self.assertEqual(len(data), 18)
        self.assertEqual(data[8:12], [VID & 0xff, VID >> 8, PID & 0xff, PID >> 8])

    @usb_domain_test_case
    def test_bulk_512_bytes_endpoints(self):
        # Configuration descriptor: data endpoints with 512-byte max packets (High-Speed bulk).
        handshake, data = yield from self.get_descriptor(0x02, length=255)
        self.assertEqual(handshake, USBPacketID.ACK)
        endpoints = []
        i = 0
        while i < len(data):
            if data[i + 1] == 0x05: # Endpoint descriptor.
                endpoints.append((data[i + 2], data[i + 4] | (data[i + 5] << 8)))
            i += data[i]
        self.assertIn((0x80 | DATA_ENDPOINT, 512), endpoints)
        self.assertIn((DATA_ENDPOINT,        512), endpoints)

    @usb_domain_test_case
    def test_bulk_out_in(self):
        dut = self.dut
        yield from self.set_configuration(1)

        # OUT: host -> rx stream.
        handshake = yield from self.out_transaction(0x12, 0x34, 0x56,
            endpoint = DATA_ENDPOINT,
            data_pid = USBPacketID.DATA0,
        )
        self.assertEqual(handshake, USBPacketID.ACK)
        yield from self.advance_cycles(100)
        self.assertEqual(self.received, [0x12, 0x34, 0x56])

        # IN: tx stream -> host.
        for byte in [0xab, 0xcd]:
            yield dut.tx.valid.eq(1)
            yield dut.tx.first.eq(byte == 0xab)
            yield dut.tx.last.eq(byte == 0xcd)
            yield dut.tx.payload.eq(byte)
            yield
            while not (yield dut.tx.ready):
                yield
        yield dut.tx.valid.eq(0)
        yield from self.advance_cycles(100)
        pid, data = yield from self.in_transaction(endpoint=DATA_ENDPOINT)
        self.assertEqual(pid, USBPacketID.DATA0)
        self.assertEqual(data, [0xab, 0xcd])

class TestLunaCDCACMUTMIHighSpeed(_UTMIDeviceTest):
    LINE_STATE = LINE_STATE_SE0 # Bus reset.

    @usb_domain_test_case
    def test_high_speed_chirp(self):
        # High-Speed capable: chirp K after the bus reset.
        self.assertIsNotNone((yield from self.chirp_cycle(20000)))

class TestLunaFullSpeedUTMIReference(_UTMIDeviceTest):
    FRAGMENT_UNDER_TEST = USBSerialDevice
    FRAGMENT_ARGUMENTS  = dict(idVendor=VID, idProduct=PID)
    LINE_STATE          = LINE_STATE_SE0

    @usb_domain_test_case
    def test_no_chirp(self):
        # Reference: LUNA's USBSerialDevice uses a raw UTMI bus at Full-Speed only (no chirp).
        self.assertIsNone((yield from self.chirp_cycle(20000)))

# LiteX Integration (Verilog conversion) -----------------------------------------------------------

class _Platform(GenericPlatform):
    def __init__(self, output_dir):
        GenericPlatform.__init__(self, "", [])
        self.output_dir = output_dir

class TestLunaCDCACMUTMIConversion(unittest.TestCase):
    def test_conversion(self):
        with tempfile.TemporaryDirectory() as output_dir:
            platform = _Platform(output_dir)
            utmi     = Record([(name, width) for name, width, _ in utmi_layout])
            dut      = LunaCDCACM(platform, utmi)
            dut.clock_domains.cd_usb = ClockDomain("usb")
            dut.finalize()

            # UTMI signals are ports of the converted LUNA core, in the "usb" domain.
            for name, _, direction in utmi_layout:
                self.assertIs(dut.core_params[f"{direction}__bus_{name}"], getattr(utmi, name))
            self.assertEqual(len(platform.sources), 1)
            with open(platform.sources[0][0], encoding="utf-8") as f:
                verilog = f.read()
            ports = re.search(r"module usb_cdc_acm\((.*?)\);", verilog, re.S).group(1)
            ports = {port.strip() for port in ports.split(",")}
            for name, _, _ in utmi_layout:
                self.assertIn(name, ports)
            self.assertIn("usb_clk", ports)
