#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Geometry lint for the generated diagram SVGs: every <text> is measured with Carlito (the metric
twin of Calibri, the diagrams' first font) and with Liberation Sans (Arial metrics, the fallback
of viewers without Calibri/Carlito, about 10% wider) and checked against the box outlines
(polygons with a stroke), the arrows (paths) and the other texts. Crossings and near misses
(closer than MARGIN px) are listed; a clean diagram prints "0 issue(s)" for both fonts. The SVGs
are embedded as they are in the wiki pages, so a label must fit with either font.

    python3 doc/diagrams/svglint.py doc/wiki/images/litex-overview.svg [...] [-v] [--fonts DIR]

-v also lists the widest texts, to size boxes. Needs Pillow and the fonts (Debian/Ubuntu:
fonts-crosextra-carlito, fonts-liberation; --fonts adds a directory holding the .ttf files).
"""

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET

try:
    from PIL import ImageFont
except ImportError:  # pragma: no cover
    sys.exit("svglint.py needs Pillow (pip install pillow / apt install python3-pil)")

FONT_SETS = {
    "Carlito":         {(None, None): "Carlito-Regular", ("bold", None): "Carlito-Bold",
                        (None, "italic"): "Carlito-Italic", ("bold", "italic"): "Carlito-BoldItalic"},
    "Liberation Sans": {(None, None): "LiberationSans-Regular", ("bold", None): "LiberationSans-Bold",
                        (None, "italic"): "LiberationSans-Italic", ("bold", "italic"): "LiberationSans-BoldItalic"},
}
FONT_DIRS = ["/usr/share/fonts/truetype/crosextra/", "/usr/share/fonts/crosextra/",
             "/usr/share/fonts/truetype/liberation/", "/usr/share/fonts/liberation/",
             "/usr/share/fonts/truetype/liberation2/", "/usr/share/fonts/liberation-sans/",
             "/usr/local/share/fonts/", os.path.expanduser("~/.fonts/"), os.path.expanduser("~/.local/share/fonts/")]
SVG    = "{http://www.w3.org/2000/svg}"
MARGIN = 4.0
_cache = {}
_extra = []
_set   = "Carlito"

def font_path(name):
    for d in _extra + FONT_DIRS:
        p = os.path.join(d, name + ".ttf")
        if os.path.exists(p):
            return p
    return None

def font(w, s, size):
    k = (_set, w, s, size)
    if k not in _cache:
        p = font_path(FONT_SETS[_set][(w, s)])
        if p is None:
            sys.exit(f"svglint.py: {_set} fonts not found (apt install fonts-crosextra-carlito fonts-liberation, or --fonts DIR)")
        _cache[k] = ImageFont.truetype(p, int(round(size)))
    return _cache[k]

def text_bbox(el):
    """(x0, y0, x1, y1, text): the ink box of a <text>, in canvas coordinates."""
    x, y = float(el.get("x")), float(el.get("y"))
    size = float(el.get("font-size", 13))
    anchor = el.get("text-anchor", "start")
    w, s = el.get("font-weight"), el.get("font-style")
    t = el.text or ""
    f = font(w, s, size)
    adv = f.getlength(t)
    asc, desc = f.getmetrics()
    ib = f.getbbox(t)
    top, bot = ib[1] - asc, ib[3] - asc        # ink, relative to the baseline
    if anchor == "middle": x0 = x - adv/2
    elif anchor == "end": x0 = x - adv
    else: x0 = x
    m = re.search(r"rotate\((-?[\d.]+)", el.get("transform", ""))
    if m and abs(float(m.group(1))) == 90:
        if float(m.group(1)) < 0:   # The text runs upward from (x, y), its ascent to the left.
            return (x + top, y - (x0 + adv - x), x + bot, y - (x0 - x), t)
        return (x - bot, y + (x0 - x), x - top, y + (x0 + adv - x), t)   # Runs downward.
    return (x0, y + top, x0 + adv, y + bot, t)

def seg_rect(x1, y1, x2, y2, r):
    """Does the segment meet the rectangle (Liang-Barsky)?"""
    rx0, ry0, rx1, ry1 = r
    dx, dy = x2 - x1, y2 - y1
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x1 - rx0), (dx, rx1 - x1), (-dy, y1 - ry0), (dy, ry1 - y1)):
        if p == 0:
            if q < 0: return False
        else:
            t = q / p
            if p < 0:
                if t > t1: return False
                if t > t0: t0 = t
            else:
                if t < t0: return False
                if t < t1: t1 = t
    return True

def inflate(r, m):
    return (r[0] - m, r[1] - m, r[2] + m, r[3] + m)

def overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

def lint(path, verbose=False):
    """Issues of path, with every font set."""
    global _set
    total = 0
    for _set in FONT_SETS:
        total += lint_with(path, verbose and _set == "Carlito")
    return total

def lint_with(path, verbose=False):
    root = ET.parse(path).getroot()
    texts = [text_bbox(e) for e in root.iter(SVG + "text")]
    polys = []
    for e in root.iter(SVG + "polygon"):
        if e.get("stroke") is None:   # Arrow heads belong to the arrows.
            continue
        polys.append([tuple(map(float, p.split(","))) for p in e.get("points").split()])
    paths = [[tuple(map(float, p.split(","))) for p in re.findall(r"[-\d.]+,[-\d.]+", e.get("d"))]
             for e in root.iter(SVG + "path")]
    images = [(float(e.get("x")), float(e.get("y")), float(e.get("x")) + float(e.get("width")),
               float(e.get("y")) + float(e.get("height"))) for e in root.iter(SVG + "image")]
    issues = 0
    # Embedded images (the logos) must not touch a box, an arrow or a label.
    for im in images:
        rm = inflate(im, MARGIN)
        for pts in polys:
            for a, b in zip(pts, pts[1:] + pts[:1]):
                if seg_rect(a[0], a[1], b[0], b[1], rm):
                    print(f"{_set}: image at {im[0]:.0f},{im[1]:.0f}-{im[2]:.0f},{im[3]:.0f} meets box edge ({a[0]:.0f},{a[1]:.0f})-({b[0]:.0f},{b[1]:.0f})")
                    issues += 1
                    break
        for pts in paths:
            for a, b in zip(pts, pts[1:]):
                if seg_rect(a[0], a[1], b[0], b[1], rm):
                    print(f"{_set}: image at {im[0]:.0f},{im[1]:.0f} meets arrow ({a[0]:.0f},{a[1]:.0f})-({b[0]:.0f},{b[1]:.0f})")
                    issues += 1
                    break
        for tb in texts:
            if overlap(rm, tb[:4]):
                print(f"{_set}: image at {im[0]:.0f},{im[1]:.0f} overlaps text '{tb[4]}'")
                issues += 1
    for tb in texts:
        r = tb[:4]
        rm = inflate(r, MARGIN)
        where = f"text '{tb[4]}' at {r[0]:.0f},{r[1]:.0f}-{r[2]:.0f},{r[3]:.0f}"
        for pts in polys:
            for a, b in zip(pts, pts[1:] + pts[:1]):
                if seg_rect(a[0], a[1], b[0], b[1], rm):
                    hard = seg_rect(a[0], a[1], b[0], b[1], r)
                    print(f"{_set}: {'CROSS' if hard else 'near '} box edge ({a[0]:.0f},{a[1]:.0f})-({b[0]:.0f},{b[1]:.0f}): {where}")
                    issues += 1
        for pts in paths:
            for a, b in zip(pts, pts[1:]):
                if seg_rect(a[0], a[1], b[0], b[1], rm):
                    hard = seg_rect(a[0], a[1], b[0], b[1], r)
                    print(f"{_set}: {'CROSS' if hard else 'near '} arrow ({a[0]:.0f},{a[1]:.0f})-({b[0]:.0f},{b[1]:.0f}): {where}")
                    issues += 1
    for i, a in enumerate(texts):
        for b in texts[i+1:]:
            if overlap(inflate(a[:4], 1.5), b[:4]):
                print(f"{_set}: OVERLAP text '{a[4]}' / '{b[4]}'")
                issues += 1
    print(f"{path} ({_set}): {len(texts)} texts, {len(polys)} boxes, {len(paths)} arrows, {len(images)} images, {issues} issue(s)")
    if verbose:
        for tb in sorted(texts, key=lambda t: t[2]-t[0], reverse=True)[:12]:
            print(f"  {tb[2]-tb[0]:6.1f} px  '{tb[4]}'")
    return issues

def main():
    parser = argparse.ArgumentParser(description="Geometry lint for LiteX diagram SVGs.")
    parser.add_argument("files", nargs="+")
    parser.add_argument("-v", "--verbose", action="store_true", help="List the widest texts.")
    parser.add_argument("--fonts", action="append", default=[], help="Extra directory with the .ttf files.")
    args = parser.parse_args()
    _extra.extend(args.fonts)
    sys.exit(1 if sum(lint(p, args.verbose) for p in args.files) else 0)

if __name__ == "__main__":
    main()
