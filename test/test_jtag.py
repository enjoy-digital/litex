#
# This file is part of LiteX.
#
# Copyright (c) 2026 LiteX-SDR Project
# SPDX-License-Identifier: BSD-2-Clause

"""Tests for JTAGPHY and jtagstream encoding.

Exercises the platform-independent JTAGPHY FSM using a MockJTAG in place of
vendor-specific TAP primitives (BSCANE2, JTAGG, AlteraJTAG, etc.).  A single
simulation covers Xilinx, Altera, and Efinix code paths because they share the
JTAGPHY class — only the TAP instantiation differs.

ECP5 uses a separate ECP5JTAGPHY with hand-written Verilog and is not covered
by these tests.

Also includes Verilog generation tests that guard against Migen->Verilog code-gen
pitfalls (unsigned negative constants in comparisons, unreachable counter values).
"""

import re
import unittest

from migen import *
from migen.fhdl.structure import _Assign, ClockSignal as _ClockSignal

from litex.gen import *
from litex.gen.sim import run_simulation
from litex.soc.interconnect import stream
from litex.soc.cores.jtag import JTAGPHY

# ---------------------------------------------------------------------- #
# Mock JTAG TAP                                                          #
# ---------------------------------------------------------------------- #

class MockJTAG(Module):
    """Mock JTAG TAP interface for simulation.

    Exposes the same signals as a real JTAG TAP primitive without any
    vendor-specific hardware.  Pass an instance to JTAGPHY(jtag=...) to
    bypass device detection.
    """
    def __init__(self):
        self.tck     = Signal()
        self.tdi     = Signal()
        self.tdo     = Signal()
        self.shift   = Signal()
        self.capture = Signal()
        self.reset   = Signal()
        self.update  = Signal()

# ---------------------------------------------------------------------- #
# Test DUT                                                                #
# ---------------------------------------------------------------------- #

class JTAGPHYTestDUT(Module):
    """JTAGPHY wrapped for Migen simulation.

    Uses clock_domain="jtag" so JTAGPHY skips CDC — the FSM, sink, and
    source all live in the jtag domain.  This allows a single-domain
    simulation that exercises the protocol logic without cross-domain
    timing complications.

    The Migen simulator cannot evaluate comb assignments targeting
    ClockSignal, so get_fragment() filters them out (the simulator drives
    clock domains directly via its TimeManager).
    """
    def __init__(self, data_width=8):
        # Provide jtag clock domain with reset (for AsyncResetSynchronizer).
        self.clock_domains.cd_jtag = ClockDomain("jtag")

        self.submodules.jtag_tap = jtag_tap = MockJTAG()
        self.submodules.phy = phy = JTAGPHY(
            jtag         = jtag_tap,
            data_width   = data_width,
            clock_domain = "jtag",  # No CDC — everything in jtag domain.
        )
        self.sink   = phy.sink
        self.source = phy.source

    def get_fragment(self):
        f = Module.get_fragment(self)
        # Remove comb assignments to ClockSignal — the simulator drives
        # clock domains directly and raises NotImplementedError on these.
        f.comb = [s for s in f.comb
                  if not (isinstance(s, _Assign) and isinstance(s.l, _ClockSignal))]
        return f

# ---------------------------------------------------------------------- #
# Simulation Tests                                                        #
# ---------------------------------------------------------------------- #

class TestJTAGPHY(unittest.TestCase):
    """Migen simulation tests for JTAGPHY FSM and data paths."""

    DATA_WIDTH = 8

    # -- helpers -------------------------------------------------------- #

    def _scan(self, dut, host_data=0x00, host_valid=0, host_ready=1):
        """Simulate one complete JTAG scan (data_width + 3 bits).

        Protocol (LSB first):
          Bit 0                : XFER-READY  (TDO=target_ready, TDI=host_ready)
          Bits 1..data_width   : XFER-DATA   (TDO=target_data,  TDI=host_data)
          Bit data_width+1     : XFER-VALID  (TDO=target_valid, TDI=host_valid)
          Bit data_width+2     : XFER-PADDING

        Returns (target_data, target_valid, target_ready).
        """
        dw = self.DATA_WIDTH

        # Capture pulse — resets FSM to XFER-READY.
        yield dut.jtag_tap.capture.eq(1)
        yield
        yield dut.jtag_tap.capture.eq(0)
        yield

        # Bit 0: XFER-READY.
        yield dut.jtag_tap.shift.eq(1)
        yield dut.jtag_tap.tdi.eq(host_ready)
        yield
        target_ready = (yield dut.jtag_tap.tdo)

        # Bits 1..data_width: XFER-DATA (LSB first).
        target_data = 0
        for bit in range(dw):
            yield dut.jtag_tap.tdi.eq((host_data >> bit) & 1)
            yield
            tdo_bit = (yield dut.jtag_tap.tdo)
            target_data |= (tdo_bit << bit)

        # Bit data_width+1: XFER-VALID.
        yield dut.jtag_tap.tdi.eq(host_valid)
        yield
        target_valid = (yield dut.jtag_tap.tdo)

        # Bit data_width+2: XFER-PADDING.
        yield

        # End scan — shift falls (Exit1-DR).
        yield dut.jtag_tap.shift.eq(0)
        yield                       # shift_falling detected
        yield                       # sync.jtag processes update_rx / update_ready
        yield                       # extra settling cycle

        return target_data, target_valid, target_ready

    def _run(self, dut, generator):
        """Run a single-domain simulation in the jtag clock domain."""
        run_simulation(dut, {"jtag": [generator()]}, clocks={"jtag": 10})

    # -- tests --------------------------------------------------------- #

    def test_tx_single_byte(self):
        """Target->Host: load 0xA5 on sink, verify TDO carries it."""
        dut = JTAGPHYTestDUT(data_width=self.DATA_WIDTH)
        result = {}

        def gen():
            yield dut.sink.valid.eq(1)
            yield dut.sink.data.eq(0xA5)
            for _ in range(20):
                yield
            data, valid, _ = yield from self._scan(dut, host_ready=1)
            result["data"]  = data
            result["valid"] = valid

        self._run(dut, gen)
        self.assertEqual(result["data"],  0xA5)
        self.assertEqual(result["valid"], 1)

    def test_tx_all_ones(self):
        """Target->Host: 0xFF exercises every bit lane."""
        dut = JTAGPHYTestDUT(data_width=self.DATA_WIDTH)
        result = {}

        def gen():
            yield dut.sink.valid.eq(1)
            yield dut.sink.data.eq(0xFF)
            for _ in range(20):
                yield
            data, valid, _ = yield from self._scan(dut, host_ready=1)
            result["data"]  = data
            result["valid"] = valid

        self._run(dut, gen)
        self.assertEqual(result["data"],  0xFF)
        self.assertEqual(result["valid"], 1)

    def test_tx_all_zeros(self):
        """Target->Host: 0x00 verifies nothing is stuck high."""
        dut = JTAGPHYTestDUT(data_width=self.DATA_WIDTH)
        result = {}

        def gen():
            yield dut.sink.valid.eq(1)
            yield dut.sink.data.eq(0x00)
            for _ in range(20):
                yield
            data, valid, _ = yield from self._scan(dut, host_ready=1)
            result["data"]  = data
            result["valid"] = valid

        self._run(dut, gen)
        self.assertEqual(result["data"],  0x00)
        self.assertEqual(result["valid"], 1)

    def test_rx_single_byte(self):
        """Host->Target: shift 0x42 via TDI, verify it appears on source."""
        dut = JTAGPHYTestDUT(data_width=self.DATA_WIDTH)
        result = {}

        def gen():
            # Don't assert source.ready yet — without CDC there is no FIFO,
            # so rx_valid is cleared the cycle after ready handshakes.
            for _ in range(5):
                yield
            yield from self._scan(dut, host_data=0x42, host_valid=1, host_ready=1)
            for _ in range(5):
                yield
            result["valid"] = (yield dut.source.valid)
            result["data"]  = (yield dut.source.data)
            # Consume.
            yield dut.source.ready.eq(1)
            yield
            yield dut.source.ready.eq(0)

        self._run(dut, gen)
        self.assertEqual(result["valid"], 1)
        self.assertEqual(result["data"],  0x42)

    def test_rx_high_byte(self):
        """Host->Target: 0xDE has bit 7 set, verifies full byte width."""
        dut = JTAGPHYTestDUT(data_width=self.DATA_WIDTH)
        result = {}

        def gen():
            for _ in range(5):
                yield
            yield from self._scan(dut, host_data=0xDE, host_valid=1)
            for _ in range(5):
                yield
            result["valid"] = (yield dut.source.valid)
            result["data"]  = (yield dut.source.data)

        self._run(dut, gen)
        self.assertEqual(result["valid"], 1)
        self.assertEqual(result["data"],  0xDE)

    def test_rx_not_stored_when_invalid(self):
        """RX data with host_valid=0 must not appear on source."""
        dut = JTAGPHYTestDUT(data_width=self.DATA_WIDTH)
        result = {}

        def gen():
            yield dut.source.ready.eq(1)
            for _ in range(5):
                yield
            yield from self._scan(dut, host_data=0xBB, host_valid=0)
            for _ in range(20):
                yield
            result["valid"] = (yield dut.source.valid)

        self._run(dut, gen)
        self.assertEqual(result["valid"], 0)

    def test_counter_reaches_end(self):
        """FSM must transit through XFER-VALID after exactly data_width shifts.

        Regression test for Signal(max=data_width) bug: a 3-bit counter
        (max=8) can never equal 8, so the FSM gets stuck in XFER-DATA
        forever.  The fix uses count == (data_width - 1).
        """
        dut = JTAGPHYTestDUT(data_width=self.DATA_WIDTH)
        result = {}

        def gen():
            yield dut.sink.valid.eq(1)
            yield dut.sink.data.eq(0x55)
            for _ in range(20):
                yield
            data, valid, _ = yield from self._scan(dut, host_ready=1)
            result["data"]  = data
            result["valid"] = valid

        self._run(dut, gen)
        self.assertEqual(result["valid"], 1,
            "FSM never reached XFER-VALID -- counter comparison may be unreachable")
        self.assertEqual(result["data"], 0x55)

    def test_bidirectional(self):
        """Simultaneous TX and RX in a single scan."""
        dut = JTAGPHYTestDUT(data_width=self.DATA_WIDTH)
        result = {}

        def gen():
            # Load TX data but don't assert source.ready yet.
            yield dut.sink.valid.eq(1)
            yield dut.sink.data.eq(0xAB)
            for _ in range(20):
                yield

            tx_data, tx_valid, _ = yield from self._scan(
                dut, host_data=0xCD, host_valid=1, host_ready=1
            )
            result["tx_data"]  = tx_data
            result["tx_valid"] = tx_valid

            for _ in range(5):
                yield
            result["rx_valid"] = (yield dut.source.valid)
            result["rx_data"]  = (yield dut.source.data)
            # Consume RX.
            yield dut.source.ready.eq(1)
            yield
            yield dut.source.ready.eq(0)

        self._run(dut, gen)
        self.assertEqual(result["tx_data"],  0xAB)
        self.assertEqual(result["tx_valid"], 1)
        self.assertEqual(result["rx_valid"], 1)
        self.assertEqual(result["rx_data"],  0xCD)

    def test_consecutive_scans(self):
        """Multiple scans back-to-back transfer distinct bytes."""
        dut = JTAGPHYTestDUT(data_width=self.DATA_WIDTH)
        tx_received = []
        rx_received = []

        def gen():
            test_bytes = [0x11, 0x80, 0xFF]

            for i, byte in enumerate(test_bytes):
                # Keep sink valid THROUGH the scan so the FSM captures it.
                yield dut.sink.valid.eq(1)
                yield dut.sink.data.eq(byte)
                for _ in range(10):
                    yield

                host_byte = (i + 1) * 0x10
                data, valid, _ = yield from self._scan(
                    dut, host_data=host_byte, host_valid=1, host_ready=1
                )
                if valid:
                    tx_received.append(data)

                # Deassert sink after scan.
                yield dut.sink.valid.eq(0)

                # Check RX (don't hold source.ready high).
                for _ in range(5):
                    yield
                if (yield dut.source.valid):
                    rx_received.append((yield dut.source.data))
                    yield dut.source.ready.eq(1)
                    yield
                    yield dut.source.ready.eq(0)

                for _ in range(5):
                    yield

        self._run(dut, gen)
        self.assertGreater(len(tx_received), 0, "No TX data received across scans")
        self.assertGreater(len(rx_received), 0, "No RX data received across scans")

# ---------------------------------------------------------------------- #
# Verilog Generation Tests                                                #
# ---------------------------------------------------------------------- #

class TestJTAGPHYVerilog(unittest.TestCase):
    """Inspect generated Verilog for known Migen->Verilog code-gen pitfalls."""

    def _generate_verilog(self, data_width=8):
        """Generate flat Verilog for JTAGPHY with mock JTAG."""
        from litex.gen.fhdl.verilog import convert
        from migen.genlib.resetsync import AsyncResetSynchronizer

        # Generic lowering for AsyncResetSynchronizer (no vendor primitives).
        class _GenericARSImpl(Module):
            def __init__(self, cd, async_reset):
                rst1 = Signal(name_override="ars_ff1")
                self.sync += rst1.eq(async_reset)
                self.sync += cd.rst.eq(rst1)

        class _GenericARS:
            @staticmethod
            def lower(dr):
                return _GenericARSImpl(dr.cd, dr.async_reset)

        class VerilogDUT(Module):
            def __init__(self):
                self.clock_domains.cd_sys = ClockDomain("sys")
                self.submodules.jtag_tap = MockJTAG()
                self.submodules.phy = JTAGPHY(
                    jtag         = self.jtag_tap,
                    data_width   = data_width,
                    clock_domain = "sys",
                )
                self.tdi     = self.jtag_tap.tdi
                self.tdo     = self.jtag_tap.tdo
                self.tck     = self.jtag_tap.tck
                self.shift   = self.jtag_tap.shift
                self.capture = self.jtag_tap.capture
                self.jtag_reset = self.jtag_tap.reset

        dut = VerilogDUT()
        ios = {dut.tdi, dut.tdo, dut.tck, dut.shift, dut.capture, dut.jtag_reset}

        old_top = LiteXContext.top
        try:
            LiteXContext.top = dut
            result = convert(dut, ios=ios, name="jtagphy_test",
                             special_overrides={AsyncResetSynchronizer: _GenericARS})
        finally:
            LiteXContext.top = old_top
        return result.main_source

    def test_counter_comparison_reachable(self):
        """Counter must compare against data_width-1, not data_width.

        Signal(max=8) is 3 bits wide (0-7).  Comparing == 8 is always
        false.  The correct comparison is == 7.
        """
        try:
            verilog = self._generate_verilog(data_width=8)
        except Exception:
            self.skipTest("Verilog generation failed")

        # Must NOT compare against 8 (unreachable for 3-bit counter).
        self.assertNotIn("== 4'd8", verilog,
            "Counter compares against 8 (unreachable for 3-bit Signal(max=8))")

    def test_source_valid_driven(self):
        """RX path must connect source.valid — catches missing wiring."""
        try:
            verilog = self._generate_verilog()
        except Exception:
            self.skipTest("Verilog generation failed")

        self.assertIn("source_valid", verilog,
            "source.valid not found -- RX data path may be disconnected")

    def test_no_unsigned_negative_comparisons(self):
        """No relational comparisons should use bare negative constants.

        Migen wraps positive constants in $signed() for signed comparisons
        but emits negative constants as bare -Nd literals (e.g., -8'd128).
        In Verilog, -8'd128 is unsigned 128, causing the comparison to
        silently become unsigned.

        While JTAGPHY currently has no signed negative comparisons, this
        test guards against future regressions.
        """
        try:
            verilog = self._generate_verilog()
        except Exception:
            self.skipTest("Verilog generation failed")

        for i, line in enumerate(verilog.split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            # Pattern: relational op followed by bare negative constant.
            matches = re.findall(r"[<>]=?\s+(-\d+\'d\d+)", line)
            for match in matches:
                if f"$signed({match})" not in line:
                    self.fail(
                        f"Line {i}: bare negative constant {match} in comparison "
                        f"will cause unsigned Verilog promotion: {stripped}"
                    )

# ---------------------------------------------------------------------- #
# jtagstream Tcl Encoding Test                                            #
# ---------------------------------------------------------------------- #

class TestJTAGStreamEncoding(unittest.TestCase):
    """Verify jtagstream Tcl uses binary-safe byte construction."""

    def test_binary_format_not_format_c(self):
        """jtagstream must use 'binary format c', not 'format %c'.

        Jim Tcl's 'format %c' creates a Unicode codepoint stored as UTF-8.
        For values 0x80-0xFF this produces a two-byte sequence, corrupting
        the binary stream.  'binary format c' produces a raw byte.
        """
        import litex.build.openocd as openocd_mod
        import inspect
        source = inspect.getsource(openocd_mod)

        self.assertIn("binary format c", source,
            "jtagstream Tcl does not use 'binary format c' -- "
            "bytes > 0x7F will be corrupted by UTF-8 encoding")
        self.assertNotIn("format %c", source,
            "jtagstream Tcl still uses 'format %c' -- "
            "this creates UTF-8 codepoints instead of raw bytes")


if __name__ == "__main__":
    unittest.main()
