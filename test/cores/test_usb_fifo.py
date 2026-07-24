#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *
from migen.fhdl.specials import Tristate

from litex.build.io import SDRTristate

from litex.soc.cores.usb_fifo import FT245PHYAsynchronous, FT245PHYSynchronous

from test.support.common import MockTristate


# Mock FT245 pads ----------------------------------------------------------------------------------

class _FT245Pads:
    """Mirror of the signals the FT245 async PHY pokes at.

    `rxf_n` / `txe_n` default high so the PHY starts with "nothing to read" and "cannot write"
    — the test generator flips them as it acts as the FTDI side of the bus.
    """
    def __init__(self, dw=8):
        self.data  = Signal(dw)
        self.rxf_n = Signal(reset=1)
        self.txe_n = Signal(reset=1)
        self.oe_n  = Signal()
        self.rd_n  = Signal()
        self.wr_n  = Signal()


class _FT245SyncDUT(Module):
    def __init__(self, pads, clk_freq=100e6):
        self.clock_domains.cd_sys = ClockDomain("sys")
        self.clock_domains.cd_usb = ClockDomain("usb")
        self.comb += [
            self.cd_sys.rst.eq(0),
            self.cd_usb.rst.eq(0),
        ]
        self.submodules.phy = FT245PHYSynchronous(pads, clk_freq, fifo_depth=8, read_time=16, write_time=16)


class _MockSDRTristateImpl(Module):
    def __init__(self, t):
        t.i_mock = Signal(len(t.io), reset=2**len(t.io) - 1)
        o        = Signal.like(t.o)
        oe       = Signal.like(t.oe)

        self.sync.usb += [
            o.eq( t.o),
            oe.eq(t.oe),
        ]
        self.comb += If(oe,
            t.io.eq(o),
        ).Else(
            t.io.eq(t.i_mock),
        )
        if t.i is not None:
            self.sync.usb += If(oe,
                t.i.eq(o),
            ).Else(
                t.i.eq(t.i_mock),
            )


class MockSDRTristate:
    @staticmethod
    def lower(t):
        return _MockSDRTristateImpl(t)


# Tests --------------------------------------------------------------------------------------------

# 100 MHz clock keeps the PHY's timing counters down to single-digit cycles.
CLK_FREQ = 100e6


class TestFT245PHYAsynchronous(unittest.TestCase):
    def test_instantiation(self):
        # Smoke test: the module builds with a plausible pad record and a real-world frequency.
        pads = _FT245Pads()
        dut  = FT245PHYAsynchronous(pads, CLK_FREQ)
        self.assertEqual(dut.sink.data.nbits,   8)
        self.assertEqual(dut.source.data.nbits, 8)

    def test_read_byte_arrives_on_source(self):
        # FTDI-side mock: hold rxf_n=0 to signal "data available", and drive `i_mock` of the
        # data tristate so the PHY's read FSM samples our chosen byte. Verify it shows up on
        # the SoC-side stream source.
        #
        # The local `rxf_n` Signal in the PHY (after MultiReg) defaults to 0, so the read FSM
        # has already armed by the time the pad's reset value (1) propagates through the
        # synchroniser. To get a deterministic byte on the source, override the i_mock reset
        # value to our wanted byte — that way the very first capture carries it instead of the
        # MockTristate default of 1.
        pads = _FT245Pads()
        wanted = 0xC3

        class _PrimedMockTristateImpl(Module):
            def __init__(self, t):
                # Same as common.MockTristate, but i_mock starts at `wanted` rather than 1.
                t.i_mock = Signal(8, reset=wanted)
                self.comb += If(t.oe,
                    t.target.eq(t.o),
                ).Else(
                    t.target.eq(t.i_mock),
                )
                if t.i is not None:
                    self.comb += If(t.oe,
                        t.i.eq(t.o),
                    ).Else(
                        t.i.eq(t.i_mock),
                    )

        class _PrimedMockTristate:
            @staticmethod
            def lower(t):
                return _PrimedMockTristateImpl(t)

        dut = FT245PHYAsynchronous(pads, CLK_FREQ)
        captured = []

        @passive
        def ftdi_side():
            yield pads.txe_n.eq(1)
            # rxf_n is already low by virtue of the MultiReg default, so the read FSM is
            # already armed at cycle 0 — no need to drive rxf_n explicitly here.
            while True:
                yield

        def consumer():
            yield dut.source.ready.eq(1)
            timeout = 0
            while not ((yield dut.source.valid) and (yield dut.source.ready)):
                yield
                timeout += 1
                self.assertLess(timeout, 200, "source never delivered a byte")
            captured.append((yield dut.source.data))

        run_simulation(dut, [consumer(), ftdi_side()], special_overrides={Tristate: _PrimedMockTristate})
        self.assertEqual(captured, [wanted])

    def test_write_byte_reaches_pads(self):
        # Push a byte into the SoC-side sink and verify the PHY drives it out on `pads.data` with
        # `wr_n` pulsed low. Uses a passive "FTDI" generator that keeps `txe_n` low (FIFO has
        # room) and captures whatever byte is presented when `wr_n` goes active.
        pads = _FT245Pads()
        dut  = FT245PHYAsynchronous(pads, CLK_FREQ)
        captured = []

        @passive
        def ftdi_side():
            # FTDI says "I can accept writes" immediately.
            yield pads.txe_n.eq(0)
            yield pads.rxf_n.eq(1)
            prev_wr_n = 1
            while True:
                cur_wr_n = (yield pads.wr_n)
                # Falling edge of wr_n — sample data.
                if prev_wr_n == 1 and cur_wr_n == 0:
                    captured.append((yield pads.data))
                prev_wr_n = cur_wr_n
                yield

        def producer():
            yield dut.sink.data.eq(0xA5)
            yield dut.sink.valid.eq(1)
            # Hold valid for a handful of cycles so the sync FIFO commits the beat.
            for _ in range(4):
                yield
            yield dut.sink.valid.eq(0)
            # Run long enough for the top FSM to switch from READ to WRITE (with MultiReg +
            # anti-starvation plumbing that takes a few cycles).
            for _ in range(200):
                yield

        run_simulation(dut, [producer(), ftdi_side()], special_overrides={Tristate: MockTristate})
        self.assertIn(0xA5, captured)


class TestFT245PHYSynchronous(unittest.TestCase):
    def _run(self, dut, generators):
        clocks = {
            "sys" : 10,
            "usb" : 10,
        }
        for cdc in [dut.phy.read_cdc, dut.phy.write_cdc]:
            clocks[f"from{cdc.duid}"] = 10
            clocks[f"to{cdc.duid}"]   = 10
        run_simulation(
            dut,
            generators,
            clocks            = clocks,
            special_overrides = {SDRTristate: MockSDRTristate},
        )

    def _producer(self, dut, payload):
        for byte in payload:
            yield dut.phy.sink.data.eq(byte)
            yield dut.phy.sink.valid.eq(1)
            while not (yield dut.phy.sink.ready):
                yield
            yield
        yield dut.phy.sink.valid.eq(0)

    def test_write_burst_has_no_leading_word(self):
        pads     = _FT245Pads()
        dut      = _FT245SyncDUT(pads)
        payload  = [0x11, 0x22, 0x33, 0x44]
        captured = []

        def ftdi_side():
            yield pads.rxf_n.eq(1)
            yield pads.txe_n.eq(0)
            for _ in range(500):
                if (yield pads.wr_n) == 0:
                    captured.append((yield pads.data))
                    if len(captured) == len(payload):
                        return
                yield
            self.fail("synchronous FT245 write burst stalled")

        self._run(dut, {
            "sys" : [self._producer(dut, payload)],
            "usb" : [ftdi_side()],
        })
        self.assertEqual(captured, payload)

    def test_write_txe_pause_keeps_prefetched_word(self):
        pads     = _FT245Pads()
        dut      = _FT245SyncDUT(pads)
        payload  = [0x10, 0x20, 0x30, 0x40]
        captured = []

        def ftdi_side():
            yield pads.rxf_n.eq(1)
            yield pads.txe_n.eq(0)
            pause_cycles = 0
            for _ in range(800):
                if (yield pads.wr_n) == 0 and (yield pads.txe_n) == 0:
                    captured.append((yield pads.data))
                    if len(captured) == 2:
                        pause_cycles = 8
                    if len(captured) == len(payload):
                        return
                if pause_cycles:
                    yield pads.txe_n.eq(1)
                    pause_cycles -= 1
                else:
                    yield pads.txe_n.eq(0)
                yield
            self.fail("synchronous FT245 write burst stalled after TXE# pause")

        self._run(dut, {
            "sys" : [self._producer(dut, payload)],
            "usb" : [ftdi_side()],
        })
        self.assertEqual(captured, payload)


if __name__ == "__main__":
    unittest.main()
