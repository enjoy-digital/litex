#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Terminal captures in the LiteX diagram style.

A capture is the text of a terminal session (a BIOS boot, a build log, a litex_cli listing) kept
in doc/diagrams/captures/<name>.txt and drawn as a dark chamfered box of monospace text, with the
usual caption and logo, by a diagram script:

    from litex_diagram import *
    from terminal import Terminal, capture

    LINES = capture("litex-sim-boot")      # doc/diagrams/captures/litex-sim-boot.txt
    W, H  = Terminal.size(LINES)           # a canvas for the box, the caption and the logo

    def draw(d):
        w, h = Terminal(d).draw(24, 24, LINES)
        d.caption(24 + w/2, 24 + h + 48, "Title", "subtitle")
        d.footer()

Why text and not a screenshot: a capture is diffable, reviewable and a few KB, the page says which
command produced it, and it reads at any zoom. Keep a capture to what the reader must see (about
25 lines, an "..." line where output is skipped) and freeze what changes from run to run (dates,
hashes, timings) when it is taken. Lines starting with a prompt ("$ ", "litex> ") are bold.
"""

import os

from litex_diagram import *

__all__ = ["Terminal", "capture", "CAPTURES", "PROMPTS", "TERM_BG", "TERM_FG", "TERM_DIM"]

CAPTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")

TERM_BG, TERM_FG, TERM_DIM = "#1e1e1e", "#e6e6e6", "#9a9a9a"
SIZE, CHAR_W, LINE_H = 12, 7.2, 15.6   # Liberation Mono at 12 px: 0.6 em advance, 1.3 em pitch.
PAD_X, PAD_Y = 18, 18
PROMPTS = ("$ ", "litex> ", "# ")

def capture(name, cols=80):
    """The lines of doc/diagrams/captures/<name>.txt (tabs expanded, trailing spaces stripped)."""
    path = os.path.join(CAPTURES, name + ".txt")
    lines = [l.expandtabs(8).rstrip() for l in open(path, encoding="utf-8").read().rstrip("\n").split("\n")]
    for l in lines:
        if len(l) > cols:
            raise ValueError(f"{path}: line longer than {cols} columns: {l!r}")
        if any(ord(c) < 32 for c in l):
            raise ValueError(f"{path}: control character in a line (strip the escape codes): {l!r}")
    return lines


class Terminal:
    """Draws a capture as a dark box of monospace text on a Diagram (80 columns by default)."""

    def __init__(self, d, cols=80):
        self.d, self.cols = d, cols

    @staticmethod
    def box_size(lines, cols=80):
        return cols*CHAR_W + 2*PAD_X, len(lines)*LINE_H + 2*PAD_Y

    @staticmethod
    def size(lines, cols=80, margin=24):
        """(width, height) of a canvas holding the box at (margin, margin), a two line caption under
        it and the LiteX logo at the bottom right."""
        w, h = Terminal.box_size(lines, cols)
        return int(w + 2*margin + 100), int(margin + h + 112)

    def draw(self, x, y, lines, prompts=PROMPTS):
        """The box with its top-left corner at (x, y); returns (width, height)."""
        w, h = self.box_size(lines, self.cols)
        self.d.box(x, y, x + w, y + h, fill=TERM_BG, c=14)
        for i, line in enumerate(lines):
            if not line:
                continue
            weight = "bold" if line.startswith(prompts) else None
            fill   = TERM_DIM if line.strip() == "..." else TERM_FG
            self.d.text(x + PAD_X, round(y + PAD_Y + SIZE + i*LINE_H, 1), line, SIZE, anchor="start",
                        weight=weight, fill=fill, family=MONO)
        return w, h
