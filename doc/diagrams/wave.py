#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Timing diagrams in the LiteX diagram style: a few signals over a few cycles, drawn from the
transitions written in the diagram script (the pedagogical waves are 8 to 16 cycles long):

    from litex_diagram import *
    from wave import Wave

    def draw(d):
        w = Wave(d, 40, 30, cycles=10)
        w.clock("sys_clk")
        w.bus("adr", {2: "0x04", 3: None})      # a value from cycle 2, idle again from cycle 3
        w.bit("we", "0010000000")               # one character per cycle: 0, 1 or x
        w.draw()
        d.caption(...)
        d.footer()

Bits are drawn high or low (x: a mid line), buses as the usual hexagons with the value in monospace
inside, the clock as a square wave. The traces are <polyline class="wave"> elements, which the lint
leaves out of its crossing checks (values sit between the traces by design); the labels are still
checked against each other.
"""

import re

from litex_diagram import *

__all__ = ["Wave", "from_vcd"]

def from_vcd(path, period=1):
    """The value of every signal of a VCD at each cycle: {name: [v0, v1, ...]}, a cycle being `period`
    VCD time steps (a LiteScope dump has two per sample). A bit is "0", "1" or "x"; a bus is an int,
    None while undefined. The VCD excerpts live in doc/diagrams/captures/."""
    ids, cur, t, rows = {}, {}, None, []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        m = re.match(r"\$var\s+\w+\s+(\d+)\s+(\S+)\s+(\S+)", line)
        if m:
            ids[m.group(2)] = m.group(3)
            continue
        if line.startswith("#"):
            if t is not None:
                rows.append((t, dict(cur)))
            t, cur = int(line[1:]), {}
        elif line.startswith("b") and " " in line:
            v, i = line[1:].split()
            cur[ids[i]] = None if ("x" in v or "z" in v) else int(v, 2)
        elif len(line) >= 2 and line[0] in "01xz" and line[1:] in ids:
            cur[ids[line[1:]]] = line[0] if line[0] in "01" else "x"
    if t is not None:
        rows.append((t, dict(cur)))
    out, state, k = {n: [] for n in ids.values()}, {}, 0
    for c in range(rows[-1][0]//period + 1):
        while k < len(rows) and rows[k][0] <= c*period:
            state.update(rows[k][1])
            k += 1
        for n in out:
            out[n].append(state.get(n))
    return out

GRID = "#d9d9d9"

class Wave:
    def __init__(self, d, x, y, cycles, cycle_w=60, row_h=30, name_w=70):
        self.d, self.x, self.y, self.cycles = d, x, y, cycles
        self.cw, self.rh, self.nw = cycle_w, row_h, name_w
        self.rows = []

    def clock(self, name="clk"):
        self.rows.append(("clock", name, None)); return self

    def bit(self, name, pattern):
        """pattern: one character per cycle, "0", "1" or "x" (don't care); the last one repeats."""
        self.rows.append(("bit", name, pattern)); return self

    def bus(self, name, values):
        """values: {cycle: label}: the label holds until the next key; None means idle (a mid line);
        the cycles before the first key are idle."""
        self.rows.append(("bus", name, values)); return self

    def bit_samples(self, name, values, start=0):
        """A bit row from per-cycle values (from_vcd), from cycle `start`."""
        v = values[start:start + self.cycles]
        return self.bit(name, "".join("x" if x is None else str(x) for x in v))

    def bus_samples(self, name, values, start=0, fmt="0x{:x}"):
        """A bus row from per-cycle values (from_vcd): one label per run of equal values."""
        d, prev = {}, object()
        for c, x in enumerate(values[start:start + self.cycles]):
            if x != prev:
                d[c] = None if x is None else fmt.format(x)
                prev = x
        return self.bus(name, d)

    @property
    def width(self):
        return self.nw + self.cycles*self.cw

    @property
    def height(self):
        return len(self.rows)*self.rh + 24   # The cycle numbers under the traces.

    def _trace(self, pts, w=1.6):
        points = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
        self.d.out.append(f'  <polyline class="wave" points="{points}" fill="none" stroke="{ARROW}" '
                          f'stroke-width="{w}" stroke-linejoin="round"/>')

    def draw(self):
        x0, n = self.x + self.nw, len(self.rows)
        for c in range(self.cycles + 1):
            self.d.line(x0 + c*self.cw, self.y, x0 + c*self.cw, self.y + n*self.rh, col=GRID, w=1, dash=True)
        for c in range(self.cycles):
            self.d.text(x0 + (c + 0.5)*self.cw, self.y + n*self.rh + 17, str(c), 11, fill=ARROW)
        for i, (kind, name, val) in enumerate(self.rows):
            ry = self.y + i*self.rh + self.rh/2
            hi, lo = ry - 9, ry + 9
            self.d.text(x0 - 10, ry + 4.5, name, 13, anchor="end")
            if kind == "clock":
                pts = []
                for c in range(self.cycles):
                    a = x0 + c*self.cw
                    pts += [(a, lo), (a, hi), (a + self.cw/2, hi), (a + self.cw/2, lo)]
                pts.append((x0 + self.cycles*self.cw, lo))
                self._trace(pts)
            elif kind == "bit":
                pts, prev = [], None
                for c in range(self.cycles):
                    v = val[min(c, len(val) - 1)]
                    yy = {"1": hi, "0": lo}.get(str(v), ry)
                    a = x0 + c*self.cw
                    if prev is None:
                        pts.append((a, yy))
                    elif prev != yy:
                        pts += [(a, prev), (a, yy)]
                    pts.append((a + self.cw, yy))
                    prev = yy
                self._trace(pts)
            else:
                keys = sorted(val)
                segs = [(k, keys[j + 1] if j + 1 < len(keys) else self.cycles, val[k]) for j, k in enumerate(keys)]
                if not keys or keys[0] > 0:
                    segs.insert(0, (0, keys[0] if keys else self.cycles, None))
                s = 4   # The slant of a bus transition.
                for a_c, b_c, label in segs:
                    a, b = x0 + a_c*self.cw, x0 + b_c*self.cw
                    if label is None:
                        self._trace([(a, ry), (b, ry)])
                    else:
                        self._trace([(a, ry), (a + s, hi), (b - s, hi), (b, ry), (b - s, lo), (a + s, lo), (a, ry)])
                        self.d.text((a + b)/2, ry + 4, str(label), 11, family=MONO)
        return self.width, self.height
