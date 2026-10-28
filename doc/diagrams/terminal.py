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
    COLS  = Terminal.fit(LINES)            # the box hugs the longest line
    TITLE, SUBTITLE = "Title", "subtitle"
    W, H  = Terminal.size(LINES, cols=COLS, caption=(TITLE, SUBTITLE))   # the canvas: box, caption, logo

    def draw(d):
        w, h = Terminal(d, cols=COLS).draw_centered(W, 24, LINES)
        d.caption(W/2, 24 + h + 48, TITLE, SUBTITLE)
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

def capture(name, cols=None):
    """The lines of doc/diagrams/captures/<name>.txt (tabs expanded, trailing spaces stripped);
    cols, when given, is the longest line accepted."""
    path = os.path.join(CAPTURES, name + ".txt")
    lines = [l.expandtabs(8).rstrip() for l in open(path, encoding="utf-8").read().rstrip("\n").split("\n")]
    for l in lines:
        if cols is not None and len(l) > cols:
            raise ValueError(f"{path}: line longer than {cols} columns: {l!r}")
        if any(ord(c) < 32 for c in l):
            raise ValueError(f"{path}: control character in a line (strip the escape codes): {l!r}")
    return lines


class Terminal:
    """Draws a capture as a dark box of monospace text on a Diagram (`cols` wide, see fit())."""

    def __init__(self, d, cols=80):
        self.d, self.cols = d, cols

    @staticmethod
    def fit(lines, minimum=40):
        """The columns a box needs for these lines: the longest one plus one, at least `minimum`, so
        that the box hugs the text instead of leaving an empty right half."""
        return max(minimum, max(len(l) for l in lines) + 1)

    @staticmethod
    def box_size(lines, cols=80):
        return cols*CHAR_W + 2*PAD_X, len(lines)*LINE_H + 2*PAD_Y

    @staticmethod
    def size(lines, cols=80, margin=24, caption=()):
        """(width, height) of a canvas holding the box, a two line caption under it (title, subtitle:
        the canvas widens so that neither reaches the logo) and the LiteX logo at the bottom right."""
        w, h = Terminal.box_size(lines, cols)
        width = w + 2*margin + 100
        for i, t in enumerate(caption):
            # The caption is centred: half of it on each side of the middle, and the logo (148 px plus
            # its margin) must fit on the right of it.
            width = max(width, int(len(t)*(11.5 if i == 0 else 7.5)) + 2*170)
        return int(width), int(margin + h + 112)

    def draw_centered(self, width, y, lines, prompts=PROMPTS):
        """The box centred in a canvas of this width, its top at y; returns (width, height) of the box."""
        w, h = self.box_size(lines, self.cols)
        return self.draw(round((width - w)/2, 1), y, lines, prompts)

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
