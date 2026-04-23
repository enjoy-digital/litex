#
# This file is part of LiteX.
#
# Copyright (c) 2026 LiteX Authors
# SPDX-License-Identifier: BSD-2-Clause

"""Unit tests for the LiteX VideoTerminal.

The terminal maintains an internal character buffer, scrolls with a circular
row pointer, interprets a minimal subset of ANSI CSI sequences and emits a
pixel stream synchronized with a video timing generator.

Tests here focus on the character-buffer (white-box) side: the UART stream
in, the terminal memory content out.  A peek read-port is attached to the
terminal's memory so tests can assert cell values directly without having to
decode the pixel stream.
"""

import unittest

from migen import *

from litex.soc.cores.video import VideoTerminal, CSIInterpreter


# Helpers ------------------------------------------------------------------------------------------

def _blank_font():
    """4 KiB zero-filled font; content is irrelevant for white-box tests."""
    return [0] * 4096


# A character sent from the UART is consumed by the terminal in at most this
# many cycles (CR/LF trigger a full-line clear which is O(term_colums)).
_IDLE_TIMEOUT = 4096


class _Harness(Module):
    """Wraps a VideoTerminal and adds a peek read-port to its memory.

    The peek port has `has_re=True` so it behaves like a normal synchronous
    read: drive adr + re one cycle, latch dat_r two cycles later.
    """

    def __init__(self, hres=80, vres=64, with_csi_interpreter=True, with_extended_csi=False,
                 visible_cols=None, font=None):
        if font is None:
            font = _blank_font()
        kwargs = dict(
            hres=hres, vres=vres, with_csi_interpreter=with_csi_interpreter,
            with_extended_csi=with_extended_csi, font=font,
        )
        if visible_cols is not None:
            kwargs["visible_cols"] = visible_cols
        self.submodules.terminal = terminal = VideoTerminal(**kwargs)
        self.peek = terminal.term_mem.get_port(has_re=True)
        self.specials += self.peek
        # Hold VTG sink idle (white-box tests don't exercise the pixel path).
        self.comb += [
            terminal.vtg_sink.valid.eq(0),
            terminal.source.ready.eq(1),
        ]
        # Pre-create the `ongoing` signals while the FSMs are still mutable
        # — `fsm.ongoing()` calls `.act(...)` under the hood and has to run
        # before finalization.
        self.fsm_idle_sig = terminal.uart_fsm.ongoing("IDLE")
        if with_csi_interpreter:
            self.csi_recopy_sig = terminal.csi_interpreter.fsm.ongoing("RECOPY")
        else:
            self.csi_recopy_sig = None
        # Convenience aliases.
        self.uart_sink       = terminal.uart_sink
        self.term_colums     = terminal.term_colums
        self.term_lines      = terminal.term_lines
        self.y_term_rollover = terminal.y_term_rollover
        self.csi_enabled     = with_csi_interpreter
        self.fifo_valid      = terminal.uart_fifo.source.valid


def _uart_send(dut, data):
    """Generator: push `data` (iterable of ints or bytes) into the UART sink."""
    if isinstance(data, str):
        data = data.encode("latin-1")
    for byte in data:
        yield dut.uart_sink.data.eq(byte)
        yield dut.uart_sink.valid.eq(1)
        yield
        # Wait for the handshake.
        while (yield dut.uart_sink.ready) == 0:
            yield
    yield dut.uart_sink.valid.eq(0)
    yield dut.uart_sink.data.eq(0)
    yield


def _wait_uart_idle(dut, max_cycles=_IDLE_TIMEOUT):
    """Generator: tick until the UART FSM is in IDLE and the char pipeline has drained.

    The power-on CLEAR-XY phase takes term_colums * term_lines cycles before
    the FSM first enters IDLE, so tests must not assume quick settling.  We
    poll `fsm.ongoing("IDLE")` and additionally require the CSI interpreter's
    FSM to be back in RECOPY and the UART FIFO to be empty.
    """
    for _ in range(max_cycles):
        in_idle    = (yield dut.fsm_idle_sig)
        csi_recopy = (yield dut.csi_recopy_sig) if dut.csi_recopy_sig is not None else 1
        fifo_valid = (yield dut.fifo_valid)
        sink_valid = (yield dut.uart_sink.valid)
        if in_idle and csi_recopy and not fifo_valid and not sink_valid:
            # Drain one extra cycle for NextValue-based updates (color etc.).
            yield
            return
        yield
    raise TimeoutError(f"UART FSM did not reach idle in {max_cycles} cycles")


def _peek(dut, col, row):
    """Generator: read the terminal memory at (col, row); returns (char, attr)."""
    adr = row * dut.term_colums + col
    yield dut.peek.adr.eq(adr)
    yield dut.peek.re.eq(1)
    yield
    yield dut.peek.re.eq(0)
    yield
    yield
    data = (yield dut.peek.dat_r)
    yield
    char = data & 0xff
    attr = (data >> 8) & 0xff
    return char, attr


def _peek_char(dut, col, row):
    char, _ = yield from _peek(dut, col, row)
    return char


def _run(dut, gens, vcd_name=None):
    """Small wrapper over migen.run_simulation that keeps test call-sites terse."""
    if not isinstance(gens, list):
        gens = [gens]
    run_simulation(dut, gens, vcd_name=vcd_name)


# Control-character codepoints used in later tests.
BEL = 0x07
BS  = 0x08
HT  = 0x09  # TAB
LF  = 0x0a
FF  = 0x0c
CR  = 0x0d
ESC = 0x1b


# Regression tests ---------------------------------------------------------------------------------

class TestVideoTerminalReset(unittest.TestCase):
    """After reset the terminal memory must be cleared to spaces before any
    UART byte is accepted.  The clear takes term_colums * term_lines cycles."""

    def test_boot_clears_buffer(self):
        dut = _Harness(hres=80, vres=32)  # 2 rows × 128 cols = 256 cells

        def gen(dut):
            # Let the RESET/CLEAR-XY phase run to completion.
            for _ in range(dut.term_colums * dut.term_lines + 8):
                yield
            for row in range(dut.term_lines):
                for col in range(dut.term_colums):
                    c = yield from _peek_char(dut, col, row)
                    self.assertEqual(c, ord(" "),
                        f"cell ({col},{row}) = {c:#x}, expected space")

        _run(dut, gen(dut))


class TestVideoTerminalWrite(unittest.TestCase):
    """Plain ASCII writes land at the expected (col, row) cells."""

    def test_single_char_at_origin(self):
        dut = _Harness(hres=80, vres=32)

        def gen(dut):
            yield from _uart_send(dut, b"A")
            yield from _wait_uart_idle(dut)
            c = yield from _peek_char(dut, 0, 0)
            self.assertEqual(c, ord("A"))
            # Cell to the right must still be a space (untouched).
            c = yield from _peek_char(dut, 1, 0)
            self.assertEqual(c, ord(" "))

        _run(dut, gen(dut))

    def test_sequence_on_first_row(self):
        dut = _Harness(hres=80, vres=32)

        def gen(dut):
            yield from _uart_send(dut, b"HELLO")
            yield from _wait_uart_idle(dut)
            for i, ch in enumerate(b"HELLO"):
                c = yield from _peek_char(dut, i, 0)
                self.assertEqual(c, ch, f"col {i} = {c:#x}, expected {ch:#x}")

        _run(dut, gen(dut))


class TestVideoTerminalLinefeed(unittest.TestCase):
    """LF moves cursor down; CR returns to column 0.  Both also touch the
    destination line (CR clears the current row, LF clears from current x to
    EOL on the new row) — that is the behavior the hardware relies on today."""

    def test_lf_then_write_goes_to_next_row(self):
        dut = _Harness(hres=80, vres=32)

        def gen(dut):
            # First char on row 0, then LF, then a char on row 1.
            yield from _uart_send(dut, bytes([ord("A"), LF, ord("B")]))
            yield from _wait_uart_idle(dut)
            self.assertEqual((yield from _peek_char(dut, 0, 0)), ord("A"))
            # After LF, INCR-Y advances y to 1 and CLEAR-X runs to the end of
            # the new row, which resets x to 0 on completion.  So 'B' lands
            # at (0, 1).
            self.assertEqual((yield from _peek_char(dut, 0, 1)), ord("B"))

        _run(dut, gen(dut))

    def test_cr_lf_sequence(self):
        dut = _Harness(hres=80, vres=32)

        def gen(dut):
            # CR first resets x and clears the line; LF moves to next row and
            # the following 'B' lands at (0,1).
            yield from _uart_send(dut, bytes([ord("A"), CR, LF, ord("B")]))
            yield from _wait_uart_idle(dut)
            # 'A' has been wiped by CR.
            self.assertEqual((yield from _peek_char(dut, 0, 0)), ord(" "))
            self.assertEqual((yield from _peek_char(dut, 0, 1)), ord("B"))

        _run(dut, gen(dut))


class TestVideoTerminalCsiColor(unittest.TestCase):
    """The minimal CSI interpreter recognises ESC[92m (green)."""

    def test_color_default_is_zero(self):
        dut = _Harness(hres=80, vres=32)

        def gen(dut):
            yield from _uart_send(dut, b"A")
            yield from _wait_uart_idle(dut)
            _, attr = yield from _peek(dut, 0, 0)
            self.assertEqual(attr & 0xf, 0)

        _run(dut, gen(dut))

    def test_color_set_green(self):
        dut = _Harness(hres=80, vres=32)

        def gen(dut):
            yield from _uart_send(dut, b"\x1b[92mB")
            yield from _wait_uart_idle(dut)
            _, attr = yield from _peek(dut, 0, 0)
            self.assertEqual(attr & 0xf, 1, "expected green (palette index 1)")

        _run(dut, gen(dut))


class TestVideoTerminalRollover(unittest.TestCase):
    """Once the cursor crosses the last line, y_term_rollover must latch to 1."""

    def test_rollover_bit_set_after_filling_screen(self):
        dut = _Harness(hres=80, vres=32)  # 2 rows

        def gen(dut):
            # Send enough LFs to advance past the last row.
            data = bytes([LF] * (dut.term_lines + 1))
            yield from _uart_send(dut, data)
            yield from _wait_uart_idle(dut)
            rollover = yield dut.y_term_rollover
            self.assertEqual(rollover, 1)

        _run(dut, gen(dut))


class TestCSIInterpreterDisable(unittest.TestCase):
    """When with_csi_interpreter=False, ESC bytes pass through as characters."""

    def test_esc_printed_when_disabled(self):
        dut = _Harness(hres=80, vres=32, with_csi_interpreter=False)

        def gen(dut):
            yield from _uart_send(dut, bytes([ESC]))
            yield from _wait_uart_idle(dut)
            # ESC is printed as a glyph at (0,0).
            c = yield from _peek_char(dut, 0, 0)
            self.assertEqual(c, ESC)

        _run(dut, gen(dut))


class TestControlCharacters(unittest.TestCase):
    """TAB/BS/BEL/FF must behave as proper control characters, not glyphs."""

    def test_tab_moves_to_next_tab_stop(self):
        dut = _Harness(hres=80, vres=32)

        def gen(dut):
            # Write 'A', then TAB, then 'B'.  With 8-column tab stops 'B'
            # should land at column 8.
            yield from _uart_send(dut, bytes([ord("A"), HT, ord("B")]))
            yield from _wait_uart_idle(dut)
            self.assertEqual((yield from _peek_char(dut, 0, 0)), ord("A"))
            self.assertEqual((yield from _peek_char(dut, 8, 0)), ord("B"))
            # The cell between must still be a space.
            self.assertEqual((yield from _peek_char(dut, 1, 0)), ord(" "))

        _run(dut, gen(dut))

    def test_backspace_moves_cursor_left(self):
        dut = _Harness(hres=80, vres=32)

        def gen(dut):
            # 'A', 'B', BS, 'C' → col 0 = 'A', col 1 = 'C' (B overwritten).
            yield from _uart_send(dut, bytes([ord("A"), ord("B"), BS, ord("C")]))
            yield from _wait_uart_idle(dut)
            self.assertEqual((yield from _peek_char(dut, 0, 0)), ord("A"))
            self.assertEqual((yield from _peek_char(dut, 1, 0)), ord("C"))

        _run(dut, gen(dut))

    def test_bel_is_ignored(self):
        dut = _Harness(hres=80, vres=32)

        def gen(dut):
            yield from _uart_send(dut, bytes([ord("A"), BEL, ord("B")]))
            yield from _wait_uart_idle(dut)
            self.assertEqual((yield from _peek_char(dut, 0, 0)), ord("A"))
            self.assertEqual((yield from _peek_char(dut, 1, 0)), ord("B"))

        _run(dut, gen(dut))

    def test_form_feed_clears_screen(self):
        dut = _Harness(hres=80, vres=32)

        def gen(dut):
            yield from _uart_send(dut, b"HELLO")
            yield from _wait_uart_idle(dut)
            yield from _uart_send(dut, bytes([FF]))
            yield from _wait_uart_idle(dut)
            for i in range(5):
                c = yield from _peek_char(dut, i, 0)
                self.assertEqual(c, ord(" "), f"col {i} not cleared: {c:#x}")

        _run(dut, gen(dut))


class TestWrapAtVisibleColumns(unittest.TestCase):
    """End-of-line wrap must honour `visible_cols`, not a hardcoded 80."""

    def test_visible_cols_40_wraps_at_40(self):
        dut = _Harness(hres=80, vres=32, visible_cols=40)

        def gen(dut):
            # Send 45 non-space chars so we can tell where the wrap happened.
            data = bytes([ord("X")] * 45)
            yield from _uart_send(dut, data)
            yield from _wait_uart_idle(dut)
            # First 40 'X' on row 0.
            for i in range(40):
                c = yield from _peek_char(dut, i, 0)
                self.assertEqual(c, ord("X"), f"row 0 col {i} = {c:#x}")
            # Col 40 on row 0 must NOT be an 'X' (wrapped before there).
            c = yield from _peek_char(dut, 40, 0)
            self.assertNotEqual(c, ord("X"))
            # Remaining 5 'X' on row 1.
            for i in range(5):
                c = yield from _peek_char(dut, i, 1)
                self.assertEqual(c, ord("X"), f"row 1 col {i} = {c:#x}")

        _run(dut, gen(dut))


class TestExtendedCSI(unittest.TestCase):
    """Extended CSI parser (multi-digit params and CUP/ED/EL/cursor-moves).

    These tests instantiate the terminal with `with_extended_csi=True`; the
    default remains the minimal interpreter for backward compatibility."""

    def test_cup_moves_cursor(self):
        dut = _Harness(hres=80, vres=64, with_extended_csi=True)

        def gen(dut):
            # ESC[2;5H — row 2, col 5 (1-indexed in ANSI → row 1, col 4).
            yield from _uart_send(dut, b"\x1b[2;5HX")
            yield from _wait_uart_idle(dut)
            c = yield from _peek_char(dut, 4, 1)
            self.assertEqual(c, ord("X"))

        _run(dut, gen(dut))

    def test_ed_clears_screen(self):
        dut = _Harness(hres=80, vres=32, with_extended_csi=True)

        def gen(dut):
            yield from _uart_send(dut, b"HELLO\x1b[2J")
            yield from _wait_uart_idle(dut)
            for i in range(5):
                c = yield from _peek_char(dut, i, 0)
                self.assertEqual(c, ord(" "), f"col {i} not cleared: {c:#x}")

        _run(dut, gen(dut))

    def test_multidigit_color_param(self):
        """The extended interpreter parses numeric params; ESC[91m and ESC[92m
        must produce different palette indices.  The minimal interpreter gets
        this wrong because it only inspects the literal bytes '9','2'."""
        dut = _Harness(hres=80, vres=32, with_extended_csi=True)

        def gen(dut):
            yield from _uart_send(dut, b"\x1b[91mA\x1b[92mB")
            yield from _wait_uart_idle(dut)
            _, attr_a = yield from _peek(dut, 0, 0)
            _, attr_b = yield from _peek(dut, 1, 0)
            # ESC[91m → palette 1 (red), ESC[92m → palette 2 (green).
            self.assertEqual(attr_a & 0xf, 1)
            self.assertEqual(attr_b & 0xf, 2)

        _run(dut, gen(dut))

    def test_color_reset_after_set(self):
        """ESC[m after ESC[92m must restore the default color.  The minimal
        interpreter can't do this because csi_bytes are never cleared."""
        dut = _Harness(hres=80, vres=32, with_extended_csi=True)

        def gen(dut):
            yield from _uart_send(dut, b"\x1b[92mA\x1b[mB")
            yield from _wait_uart_idle(dut)
            _, attr_a = yield from _peek(dut, 0, 0)
            _, attr_b = yield from _peek(dut, 1, 0)
            self.assertEqual(attr_a & 0xf, 2, "ESC[92m → green (palette 2)")
            self.assertEqual(attr_b & 0xf, 0, "ESC[m → default color")

        _run(dut, gen(dut))

    def test_cursor_up_down(self):
        dut = _Harness(hres=80, vres=64, with_extended_csi=True)

        def gen(dut):
            # Write 'A' at (0,0), cursor down 2, write 'B' → (1, 2).
            yield from _uart_send(dut, b"A\x1b[2BB")
            yield from _wait_uart_idle(dut)
            self.assertEqual((yield from _peek_char(dut, 0, 0)), ord("A"))
            self.assertEqual((yield from _peek_char(dut, 1, 2)), ord("B"))

        _run(dut, gen(dut))


if __name__ == "__main__":
    unittest.main()
