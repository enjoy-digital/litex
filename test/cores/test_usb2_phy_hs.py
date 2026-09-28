#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import random
import unittest

from migen import *

from litex.gen.sim import run_simulation

from litex.soc.cores.usb2_phy.hs import USBHSTXEncoder, USBHSDataRecovery, USBHSRXDecoder, USBHSPHY, BITS_PER_CYCLE

# USB HS Line Model (USB 2.0, 7.1) -----------------------------------------------------------------

J, K = 1, 0

def decode_hs(levels):
    """Line levels (1: J, 0: K, from the first driven bit) -> packet bytes (SYNC/EOP checked)."""
    # NRZI decoding (reference: J before the packet).
    bits, prev = [], J
    for level in levels:
        bits.append(int(level == prev))
        prev = level
    # SYNC: 0s ending with a 1 (at least 12 0s).
    first_one = bits.index(1)
    assert first_one >= 12, "SYNC too short."
    bits = bits[first_one + 1:]
    # Unstuffing until EOP (seven 1s with no stuffed 0: bit stuffing error).
    data, ones = [], 1 # The SYNC's last bit counts.
    for i, bit in enumerate(bits):
        if ones == 6:
            if bit == 0:
                ones = 0
                continue
            # EOP: 0 + seven 1s (the 0 and six 1s already collected).
            assert data[-7:] == [0, 1, 1, 1, 1, 1, 1], "Invalid EOP."
            data = data[:-7]
            break
        ones = ones + 1 if bit else 0
        data.append(bit)
    else:
        raise AssertionError("No EOP.")
    assert len(data) % 8 == 0, f"Not a byte multiple ({len(data)} bits)."
    return [sum(data[8*n + b] << b for b in range(8)) for n in range(len(data)//8)]

def encode_hs(data, sof=False):
    """Packet bytes -> line levels (SYNC, NRZI/stuffed data, EOP: 8 bits, 40 for SOFs)."""
    bits   = [0]*31 + [1]
    stream = [(byte >> i) & 1 for byte in data for i in range(8)]
    levels, level, ones = [], J, 0
    for bit in bits + stream:
        if bit:
            ones += 1
        else:
            ones, level = 0, 1 - level
        levels.append(level)
        if ones == 6:
            ones, level = 0, 1 - level
            levels.append(level)
    eop = [0] + [1]*(39 if sof else 7)
    for bit in eop:
        level = level if bit else 1 - level
        levels.append(level)
    return levels

def oversample(levels, phase=0.0, ppm=0, jitter=0.0, rng=None, idle=64):
    """Line levels (480 Mbps) -> 16-sample words (1.92 Gsps, idle reads 0): phase in samples, each
    bit boundary jittered by +-jitter samples."""
    rng     = rng or random.Random(0)
    ratio   = 0.25*(1 + ppm*1e-6)
    bounds  = [k + rng.uniform(-jitter, jitter)/4 for k in range(len(levels) + 1)]
    samples = [0]*idle
    m, index = 0, 0
    while True:
        t = m*ratio - phase/4 # Time in bits.
        if t >= len(levels):
            break
        while index < len(levels) - 1 and t >= bounds[index + 1]:
            index += 1
        samples.append(levels[index] if t >= bounds[0] else 0)
        m += 1
    samples += [0]*idle
    samples += [0]*(-len(samples) % 16)
    return [sum(samples[16*w + i] << i for i in range(16)) for w in range(len(samples)//16)]

class _HSRX(Module):
    def __init__(self):
        self.submodules.dru = dru = USBHSDataRecovery()
        self.submodules.dec = dec = USBHSRXDecoder()
        self.comb += [
            dec.bits.eq(dru.bits),
            dec.valid_bits.eq(dru.valid),
            dec.idle.eq(dru.idle),
            dru.relock.eq(dec.eop),
        ]

def run_hs_rx(words):
    dut = _HSRX()
    res = {"packets": [], "errors": 0}

    def gen():
        packet = None
        for w in words + [0]*32:
            yield dut.dru.samples.eq(w)
            yield
            if (yield dut.dec.start):
                packet = []
            if (yield dut.dec.valid):
                packet.append((yield dut.dec.data))
            if (yield dut.dec.end):
                res["errors"] += (yield dut.dec.error)
                res["packets"].append(packet)
                packet = None

    run_simulation(dut, gen())
    return res

# Helpers ------------------------------------------------------------------------------------------

def run_tx_encoder(packets, raw=False, throttle=None, gap=40):
    """Send packets (UTMI-like byte stream + EOP marker), return the driven line levels per packet."""
    dut = USBHSTXEncoder()
    res = {"packets": [], "levels": []}
    rng = random.Random(0)

    def source():
        yield dut.raw.eq(raw)
        for data in packets:
            for n, byte in enumerate(list(data) + [None]):
                if throttle is not None:
                    while rng.random() < throttle:
                        yield dut.sink_valid.eq(0)
                        yield
                yield dut.sink_valid.eq(1)
                yield dut.sink_eop.eq(byte is None)
                yield dut.sink_data.eq(0 if byte is None else byte)
                yield
                while not (yield dut.sink_ready):
                    yield
            yield dut.sink_valid.eq(0)
            for _ in range(gap):
                yield

    @passive
    def monitor():
        levels = []
        while True:
            if (yield dut.oe):
                line = (yield dut.line)
                levels += [(line >> i) & 1 for i in range(BITS_PER_CYCLE)]
            elif levels:
                res["levels"].append(levels)
                levels = []
            yield

    run_simulation(dut, [source(), monitor()])
    return res["levels"]

# TX Encoder ---------------------------------------------------------------------------------------

class TestUSBHSTXEncoder(unittest.TestCase):
    def test_packets(self):
        rng     = random.Random(1)
        packets = [
            [0xd2],                                       # Handshake.
            [0xc3, 0x00, 0x01, 0x02, 0x03, 0xaa, 0x55],   # Data.
            [0x4b] + [0xff]*64,                           # Long 1s runs (stuffing).
            [0xc3] + [rng.randrange(256) for _ in range(512)],
            [0xc3, 0x3f, 0xfc],                           # Stuffing right before the EOP.
        ]
        levels = run_tx_encoder(packets)
        self.assertEqual(len(levels), len(packets))
        for data, lv in zip(packets, levels):
            self.assertEqual(decode_hs(lv), data)

    def test_throttled_source(self):
        # Bytes not always available (UTMI/CDC jitter): no gap in the line as long as the buffer holds.
        rng    = random.Random(2)
        data   = [0xc3] + [rng.randrange(256) for _ in range(64)]
        levels = run_tx_encoder([data], throttle=0.1)
        self.assertEqual(decode_hs(levels[0]), data)

    def test_raw_chirp(self):
        # OpMode 10: 0x00 bytes -> continuous K, no SYNC/EOP.
        levels = run_tx_encoder([[0x00]*16], raw=True)
        self.assertEqual(len(levels), 1)
        self.assertEqual(set(levels[0]), {K})
        self.assertGreaterEqual(len(levels[0]), 16*8)

# RX -----------------------------------------------------------------------------------------------

class TestUSBHSRX(unittest.TestCase):
    def check(self, packets, **kwargs):
        rng   = random.Random(3)
        words = []
        for data in packets:
            words += oversample(encode_hs(data), rng=rng, **kwargs)
        res = run_hs_rx(words)
        self.assertEqual(res["packets"], packets)
        self.assertEqual(res["errors"], 0)

    def test_rx_phases(self):
        for phase in [0, 1, 2, 3]:
            with self.subTest(phase=phase):
                self.check([[0xc3, 0x12, 0x34, 0xff, 0x00, 0x7e]], phase=phase)

    def test_rx_ppm(self):
        rng  = random.Random(4)
        data = [0xc3] + [rng.randrange(256) for _ in range(512)]
        for ppm in [-500, 500]:
            with self.subTest(ppm=ppm):
                self.check([data], phase=1.5, ppm=ppm)

    def test_rx_jitter(self):
        # +-0.5 samples (+-0.12 UI) edge jitter with +-500 ppm.
        rng  = random.Random(5)
        data = [0x4b] + [rng.randrange(256) for _ in range(512)]
        for ppm in [-500, 500]:
            with self.subTest(ppm=ppm):
                self.check([data], phase=0.5, ppm=ppm, jitter=0.5)

    def test_rx_stuffing(self):
        self.check([[0xc3] + [0xff]*32, [0xd2], [0xc3, 0x3f, 0xfc]])

    def test_rx_sof_eop(self):
        rng   = random.Random(6)
        words = oversample(encode_hs([0xa5, 0x12, 0x34], sof=True), rng=rng)
        res   = run_hs_rx(words)
        self.assertEqual(res["packets"], [[0xa5, 0x12, 0x34]])
        self.assertEqual(res["errors"], 0)

    def test_tx_rx_loopback(self):
        rng     = random.Random(7)
        packets = [[0xc3] + [rng.randrange(256) for _ in range(64)], [0xd2]]
        levels  = run_tx_encoder(packets)
        words   = []
        for lv in levels:
            words += oversample(lv, phase=2.5, ppm=-200, rng=rng)
        res = run_hs_rx(words)
        self.assertEqual(res["packets"], packets)

# UTMI (60 MHz) <-> line (120 MHz) -----------------------------------------------------------------

class _HSPHYLoopback(Module):
    """TX line (4 states/cycle) serialized x4 into the RX samples (with a few cycles of delay), from
    ``phy`` to ``peer`` (``peer`` = ``phy``: echo)."""
    def __init__(self, echo=False):
        self.submodules.phy  = phy  = USBHSPHY(cd_utmi="usb", cd_hs="usb_hs")
        self.submodules.peer = peer = phy if echo else USBHSPHY(cd_utmi="usb", cd_hs="usb_hs")
        self.clock_domains.cd_usb    = ClockDomain()
        self.clock_domains.cd_usb_hs = ClockDomain()
        delay = [Signal(16) for _ in range(3)]
        samples = Signal(16)
        self.comb += samples.eq(Mux(phy.tx_oe,
            Cat(*[Replicate(phy.tx_line[i], 4) for i in range(4)]), 0))
        self.sync.usb_hs += [delay[0].eq(samples)] + [delay[i].eq(delay[i - 1]) for i in range(1, 3)]
        self.comb += peer.rx_samples.eq(delay[-1])

class TestUSBHSPHYUTMI(unittest.TestCase):
    def test_utmi_loopback(self):
        dut     = _HSPHYLoopback()
        rng     = random.Random(8)
        packets = [[0xd2], [0xc3] + [rng.randrange(256) for _ in range(64)], [0x4b] + [0xff]*16]
        res     = {"packets": [], "errors": 0}

        def tx():
            for data in packets:
                for byte in data:
                    yield dut.phy.tx_valid.eq(1)
                    yield dut.phy.tx_data.eq(byte)
                    yield
                    while not (yield dut.phy.tx_ready):
                        yield
                yield dut.phy.tx_valid.eq(0)
                for _ in range(200):
                    yield

        @passive
        def rx():
            packet = None
            while True:
                if (yield dut.peer.rx_active):
                    if packet is None:
                        packet = []
                    if (yield dut.peer.rx_valid):
                        packet.append((yield dut.peer.rx_data))
                elif packet is not None:
                    res["packets"].append(packet)
                    packet = None
                res["errors"] += (yield dut.peer.rx_error)
                yield

        run_simulation(dut, {"usb": [tx(), rx()]}, clocks={"usb": 16, "usb_hs": 8})
        self.assertEqual(res["packets"], packets)
        self.assertEqual(res["errors"], 0)

    def test_no_rx_echo(self):
        # The TX line looped back to RX (echo): no RX activity.
        dut = _HSPHYLoopback(echo=True)
        res = {"active": 0}

        def tx():
            for byte in [0xc3, 0x12, 0x34, 0x56, 0x78]:
                yield dut.phy.tx_valid.eq(1)
                yield dut.phy.tx_data.eq(byte)
                yield
                while not (yield dut.phy.tx_ready):
                    yield
            yield dut.phy.tx_valid.eq(0)
            for _ in range(200):
                yield

        @passive
        def rx():
            while True:
                res["active"] += (yield dut.phy.rx_active)
                yield

        run_simulation(dut, {"usb": [tx(), rx()]}, clocks={"usb": 16, "usb_hs": 8})
        self.assertEqual(res["active"], 0)
