#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import random
import unittest

from migen import *

from litex.gen.sim import run_simulation

from litex.soc.cores.usb2_phy.fs import USBFSPHY, LINE_SE0, LINE_J, LINE_K, LINE_SE1

# USB Line Model (USB 2.0, 7.1) --------------------------------------------------------------------

CLK_FREQ = 60e6

def bit_rate(low_speed):
    return 1.5e6 if low_speed else 12e6

def jk(low_speed):
    return (LINE_K, LINE_J) if low_speed else (LINE_J, LINE_K)

def encode_packet(data, low_speed=False, stuff_error_at=None):
    """Bytes -> line states per bit: SYNC, NRZI/bit stuffed data, EOP (SE0 SE0 J)."""
    j, k   = jk(low_speed)
    bits   = [(byte >> i) & 1 for byte in [0x80] + list(data) for i in range(8)]
    states = []
    state  = j
    ones   = 0
    for n, bit in enumerate(bits):
        if bit:
            ones += 1
        else:
            ones  = 0
            state = k if state == j else j
        states.append(state)
        if ones == 6:
            ones = 0
            if stuff_error_at is not None and n >= stuff_error_at:
                stuff_error_at = None # No transition: stuff error.
            else:
                state = k if state == j else j
            states.append(state)
    return states + [LINE_SE0, LINE_SE0, j]

def add_skew(samples, rng):
    """D+/D- skew: transient SE0/SE1 sample at each J <-> K transition."""
    out = []
    for prev, cur in zip([samples[0]] + samples, samples):
        if {prev, cur} == {LINE_J, LINE_K} and rng.random() < 0.8:
            out[-1] = rng.choice([LINE_SE0, LINE_SE1])
        out.append(cur)
    return out

def to_samples(states, low_speed=False, phase=0.0, ppm=0, idle_before=20, idle_after=40):
    """Line states per bit -> line states per 60MHz clock (bit rate offset by ppm, packet start
    delayed by phase bits)."""
    j, _    = jk(low_speed)
    rate    = bit_rate(low_speed)*(1 + ppm*1e-6)
    samples = [j]*idle_before
    n = 0
    while True:
        position = n*rate/CLK_FREQ - phase
        index    = int(position) if position >= 0 else -1
        if index >= len(states):
            break
        samples.append(j if index < 0 else states[index])
        n += 1
    return samples + [j]*idle_after

def decode_samples(samples, low_speed=False):
    """Line states per 60MHz clock (driven periods) -> (bytes, bit periods, EOP ok)."""
    j, k    = jk(low_speed)
    period  = CLK_FREQ/bit_rate(low_speed)
    runs    = []
    for s in samples:
        if runs and runs[-1][0] == s:
            runs[-1][1] += 1
        else:
            runs.append([s, 1])
    periods = [length/period for _, length in runs]
    states  = []
    for s, length in runs:
        states += [s]*round(length/period)
    # NRZI decoding / unstuffing (from the idle J).
    bits, prev, ones, i = [], j, 0, 0
    while i < len(states) and states[i] in [j, k]:
        bit  = int(states[i] == prev)
        prev = states[i]
        i   += 1
        if ones == 6:
            assert bit == 0, "Missing stuffed bit."
            ones = 0
            continue
        ones = ones + 1 if bit else 0
        bits.append(bit)
    eop_ok = states[i:i + 3] == [LINE_SE0, LINE_SE0, j]
    assert bits[:8] == [0, 0, 0, 0, 0, 0, 0, 1], "Invalid SYNC."
    bits  = bits[8:]
    data  = [sum(bits[8*n + b] << b for b in range(8)) for n in range(len(bits)//8)]
    return data, periods, eop_ok

# Helpers ------------------------------------------------------------------------------------------

def run_rx(samples, low_speed=False):
    dut = USBFSPHY()
    res = {"bytes": [], "errors": 0, "active": []}

    def gen():
        yield dut.xcvr_select.eq(0b10 if low_speed else 0b01)
        for s in samples:
            yield dut.dp_i.eq(s & 1)
            yield dut.dn_i.eq(s >> 1)
            yield
            if (yield dut.rx_valid):
                res["bytes"].append((yield dut.rx_data))
            res["errors"] += (yield dut.rx_error)
            res["active"].append((yield dut.rx_active))

    run_simulation(dut, gen())
    return res

def run_tx(packets, low_speed=False, op_mode=0, gap=100):
    dut = USBFSPHY()
    res = {"samples": [], "oe": [], "readies": 0}

    def tx():
        yield dut.xcvr_select.eq(0b10 if low_speed else 0b01)
        yield dut.op_mode.eq(op_mode)
        for data in packets:
            for byte in data:
                yield dut.tx_valid.eq(1)
                yield dut.tx_data.eq(byte)
                yield
                for _ in range(1000):
                    if (yield dut.tx_ready):
                        break
                    yield
            yield dut.tx_valid.eq(0)
            for _ in range(gap*(8 if low_speed else 1)):
                yield

    @passive
    def monitor():
        while True:
            oe = (yield dut.oe)
            res["oe"].append(oe)
            if oe:
                res["samples"].append((yield dut.dp_o) | ((yield dut.dn_o) << 1))
            res["readies"] += (yield dut.tx_ready)
            yield

    run_simulation(dut, [tx(), monitor()])
    return res

def random_packet(rng, n):
    return [rng.choice([0x00, 0xff, rng.randrange(256)]) for _ in range(n)]

# RX -----------------------------------------------------------------------------------------------

class TestUSBFSPHYRX(unittest.TestCase):
    def test_rx_packets(self):
        rng = random.Random(0)
        for low_speed in [False, True]:
            for phase in [0.0, 0.25, 0.5, 0.75]:
                for ppm in [-2500, 0, 2500]:
                    with self.subTest(low_speed=low_speed, phase=phase, ppm=ppm):
                        data    = random_packet(rng, 16)
                        samples = to_samples(encode_packet(data, low_speed), low_speed, phase, ppm)
                        res     = run_rx(samples, low_speed)
                        self.assertEqual(res["bytes"], data)
                        self.assertEqual(res["errors"], 0)
                        self.assertFalse(res["active"][-1])

    def test_rx_skew(self):
        # Transient SE0/SE1 at the transitions (D+/D- skew), including the SOP.
        rng = random.Random(7)
        for n in range(8):
            with self.subTest(n=n):
                data    = random_packet(rng, 24)
                samples = add_skew(to_samples(encode_packet(data), phase=rng.random()), rng)
                res     = run_rx(samples)
                self.assertEqual(res["bytes"], data)
                self.assertEqual(res["errors"], 0)

    def test_rx_bit_stuffing(self):
        # Long runs of 1s (stuffed bits), including across bytes and at the end of the packet.
        for data in [[0xff]*8, [0x7e, 0xff, 0x3f], [0x01, 0xfc, 0xff]]:
            with self.subTest(data=data):
                res = run_rx(to_samples(encode_packet(data)))
                self.assertEqual(res["bytes"], data)
                self.assertEqual(res["errors"], 0)

    def test_rx_back_to_back_packets(self):
        samples = []
        for data in [[0x2d, 0x00, 0x10], [0xc3, 0x80, 0x06], [0xd2]]:
            samples += to_samples(encode_packet(data), idle_before=4, idle_after=4)
        res = run_rx(samples)
        self.assertEqual(res["bytes"], [0x2d, 0x00, 0x10, 0xc3, 0x80, 0x06, 0xd2])
        active = res["active"]
        self.assertEqual(sum(1 for a, b in zip(active, active[1:]) if not a and b), 3)

    def test_rx_stuff_error(self):
        res = run_rx(to_samples(encode_packet([0xff, 0xff], stuff_error_at=8)))
        self.assertGreater(res["errors"], 0)

    def test_rx_partial_byte_error(self):
        states = encode_packet([0x5a, 0x33])
        # Truncate in the middle of the 2nd byte, then EOP.
        states = states[:8 + 8 + 4] + [LINE_SE0, LINE_SE0, LINE_J]
        res = run_rx(to_samples(states))
        self.assertEqual(res["bytes"], [0x5a])
        self.assertGreater(res["errors"], 0)

# TX -----------------------------------------------------------------------------------------------

class TestUSBFSPHYTX(unittest.TestCase):
    def test_tx_packets(self):
        rng = random.Random(1)
        for low_speed in [False, True]:
            with self.subTest(low_speed=low_speed):
                data = random_packet(rng, 12) + [0xff, 0xff] # Ends with a stuffed bit.
                res  = run_tx([data], low_speed)
                decoded, periods, eop_ok = decode_samples(res["samples"], low_speed)
                self.assertEqual(decoded, data)
                self.assertTrue(eop_ok)
                self.assertTrue(all(abs(p - round(p)) < 1e-9 for p in periods)) # Exact bit periods.
                self.assertEqual(res["readies"], len(data))

    def test_tx_bit_stuffing(self):
        for data in [[0xff]*4, [0x3f, 0xfe], [0x80, 0x7f]]:
            with self.subTest(data=data):
                decoded, _, eop_ok = decode_samples(run_tx([data])["samples"])
                self.assertEqual(decoded, data)
                self.assertTrue(eop_ok)

    def test_tx_non_driving(self):
        res = run_tx([[0x55, 0xaa]], op_mode=0b01, gap=10)
        self.assertEqual(sum(res["oe"]), 0)
        self.assertEqual(res["readies"], 0)

    def test_tx_raw(self):
        # Bit stuffing/NRZI disabled: bits sent as J (1) / K (0), no SYNC/EOP.
        res = run_tx([[0x0f]], op_mode=0b10, gap=60)
        states = res["samples"][::5]
        self.assertEqual(states, [LINE_J]*4 + [LINE_K]*4)

# Loopback -----------------------------------------------------------------------------------------

class TestUSBFSPHYLoopback(unittest.TestCase):
    def test_loopback(self):
        rng  = random.Random(2)
        data = random_packet(rng, 32)
        tx   = run_tx([data])
        rx   = run_rx([LINE_J]*10 + tx["samples"] + [LINE_J]*20)
        self.assertEqual(rx["bytes"], data)
        self.assertEqual(rx["errors"], 0)
