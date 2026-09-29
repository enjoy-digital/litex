#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import re
import random
import unittest

from migen import *
from migen.fhdl.specials import Tristate

from litex.gen.fhdl import verilog
from litex.gen.sim  import run_simulation

from litex.build.xilinx.common import xilinx_special_overrides, xilinx_s7_special_overrides

from litex.soc.cores.usb2_phy.phy import USB2PHY
from litex.soc.cores.usb2_phy.fs  import LINE_J

from test.cores.test_usb2_phy_fs import encode_packet, to_samples, decode_samples, random_packet

# Helpers ------------------------------------------------------------------------------------------

FS_PADS = ["fs_dp", "fs_dn", "pullup"]

def fs_only_dut():
    pads = Record([(name, 1) for name in FS_PADS])
    return pads, USB2PHY(pads, with_hs=False)

def fs_only_top():
    pads, phy = fs_only_dut()
    top = Module()
    top.clock_domains.cd_usb = ClockDomain()
    top.submodules.phy = phy
    return pads, top, {*pads.flatten(), top.cd_usb.clk, top.cd_usb.rst}

def sim_tristates(pads):
    """Tristate lowering for simulation: pad input driven by the testbench (``i``), pad output and
    output enable observed (``o``/``oe``)."""
    lines = {name: Record([("i", 1), ("o", 1), ("oe", 1)]) for name in FS_PADS}
    class SimTristate:
        @staticmethod
        def lower(t):
            line = [lines[name] for name in FS_PADS if getattr(pads, name) is t.target][0]
            m    = Module()
            m.comb += [line.o.eq(t.o), line.oe.eq(t.oe)]
            if t.i is not None:
                m.comb += t.i.eq(line.i)
            return m
    return lines, {Tristate: SimTristate}

def run(dut, pads, generators):
    lines, overrides = sim_tristates(pads)
    run_simulation(dut, {"usb": [g(lines) for g in generators]}, clocks={"usb": 1e9/60e6},
        special_overrides=overrides)

def drive(lines, state):
    yield lines["fs_dp"].i.eq(state & 1)
    yield lines["fs_dn"].i.eq(state >> 1)

# USB 2.0 PHY (Full-Speed only) --------------------------------------------------------------------

class TestUSB2PHYFullSpeedOnly(unittest.TestCase):
    def test_conversion(self):
        # No SerDes/High-Speed pads: generic Tristate only (converts without vendor lowering).
        pads, top, ios = fs_only_top()
        v = str(verilog.convert(top, ios=ios))
        for name in FS_PADS:
            self.assertIsNotNone(re.search(rf"inout\s+wire\s+pads_{name}", v))
        self.assertNotIn("SerDes", v)

    def test_xilinx_conversion(self):
        pads, top, ios = fs_only_top()
        v = str(verilog.convert(top,
            ios               = ios,
            special_overrides = {**xilinx_special_overrides, **xilinx_s7_special_overrides},
        ))
        self.assertEqual(len(re.findall(r"\nIOBUF ", v)), len(FS_PADS))

    def test_high_speed_pads_released(self):
        # Full-Speed only on a High-Speed board circuit: High-Speed driver disabled.
        pads = Record([(name, 1) for name in ["d_p", "d_n", "se_dp", "se_dn"] + FS_PADS])
        top  = Module()
        top.clock_domains.cd_usb = ClockDomain()
        top.submodules.phy = USB2PHY(pads, with_hs=False)
        v = str(verilog.convert(top,
            ios               = {*pads.flatten(), top.cd_usb.clk, top.cd_usb.rst},
            special_overrides = {**xilinx_special_overrides, **xilinx_s7_special_overrides},
        ))
        v = re.sub(r"\s+", "", v)
        self.assertTrue(re.search(r"IOBUFDSIOBUFDS\(.*?\.T\(\(~1'd0\)\)", v))

    def test_rx(self):
        pads, dut = fs_only_dut()
        data      = random_packet(random.Random(0), 16)
        samples   = to_samples(encode_packet(data), phase=0.3)
        received  = []

        def gen(lines):
            yield dut.xcvr_select.eq(0b01)
            yield dut.term_select.eq(1)
            for s in samples:
                yield from drive(lines, s)
                yield
                if (yield dut.rx_valid):
                    received.append((yield dut.rx_data))
            self.assertEqual((yield dut.line_state), LINE_J)
            self.assertEqual((yield lines["pullup"].oe), 1)
            self.assertEqual((yield lines["pullup"].o),  1)

        run(dut, pads, [gen])
        self.assertEqual(received, data)

    def test_tx(self):
        pads, dut = fs_only_dut()
        data      = random_packet(random.Random(1), 16)
        samples   = []

        def tx(lines):
            yield dut.xcvr_select.eq(0b01)
            yield dut.term_select.eq(1)
            yield from drive(lines, LINE_J)
            for byte in data:
                yield dut.tx_valid.eq(1)
                yield dut.tx_data.eq(byte)
                yield
                while not (yield dut.tx_ready):
                    yield
            yield dut.tx_valid.eq(0)
            for _ in range(100):
                yield

        @passive
        def monitor(lines):
            while True:
                if (yield lines["fs_dp"].oe):
                    samples.append((yield lines["fs_dp"].o) | ((yield lines["fs_dn"].o) << 1))
                yield

        run(dut, pads, [tx, monitor])
        decoded, _, eop_ok = decode_samples(samples)
        self.assertEqual(decoded, data)
        self.assertTrue(eop_ok)

    def test_high_speed_chirp_discarded(self):
        # XcvrSelect High-Speed (device chirp K): TX acknowledged but not driven, the host doesn't
        # see a High-Speed capable device.
        pads, dut = fs_only_dut()
        res       = {"readies": 0, "driven": 0}

        def gen(lines):
            yield from drive(lines, 0b00) # Bus reset (SE0).
            yield dut.xcvr_select.eq(0b00)
            yield dut.term_select.eq(1)
            yield dut.op_mode.eq(0b10)
            yield dut.tx_data.eq(0x00)
            yield dut.tx_valid.eq(1)
            for _ in range(1000):
                yield
                res["readies"] += (yield dut.tx_ready)
                res["driven"]  += (yield lines["fs_dp"].oe) | (yield lines["fs_dn"].oe)
            self.assertEqual((yield dut.line_state), 0b00)
            self.assertEqual((yield lines["pullup"].o), 1)

        run(dut, pads, [gen])
        self.assertEqual(res["readies"], 1000)
        self.assertEqual(res["driven"],  0)
