#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""Build the wiki diagrams: run every doc/diagrams/<name>.py (SVG into doc/wiki/images/) and lint
the SVGs with svglint.py. The pages embed the SVGs (small, text, diffable); --png also exports
PNGs with Inkscape into doc/diagrams/build/ (not committed) for posts, slides and previews.

    python3 doc/diagrams/build.py                 # SVGs + lint (needs Pillow, Carlito and Liberation fonts)
    python3 doc/diagrams/build.py --only NAME     # one diagram
    python3 doc/diagrams/build.py --check         # CI: SVGs regenerate identically and lint clean
    python3 doc/diagrams/build.py --png           # + PNG exports (needs Inkscape)
"""

import argparse
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile

HERE   = os.path.dirname(os.path.abspath(__file__))
IMAGES = os.path.normpath(os.path.join(HERE, "..", "wiki", "images"))
PNGS   = os.path.join(HERE, "build")

# Diagram -> PNG export width (--png; about twice the canvas, crisp on HiDPI screens).
DIAGRAMS = {
    "litex-overview":      2800,
    "litex-ecosystem-map": 2800,
    "litex-soc-architecture": 2800,
    "litex-build-flow":        2800,
    "litex-host-bridges":      2800,
    "litex-bios-boot":         2800,
    "litex-simulation":        2800,
    "litex-streams":           2800,
    "litex-buses":             2800,
    "litex-csr-bus":           2800,
    "litex-axi":               2800,
}

def run(cmd, **kw):
    r = subprocess.run(cmd, text=True, capture_output=True, **kw)
    if r.returncode != 0:
        print(r.stdout, r.stderr, sep="\n", file=sys.stderr)
        raise SystemExit(f"failed: {' '.join(cmd)}")
    return r.stdout

def generate(name, out):
    run([sys.executable, os.path.join(HERE, f"{name}.py"), "--out", out])
    return os.path.join(out, f"{name}.svg")

def lint(svgs):
    r = subprocess.run([sys.executable, os.path.join(HERE, "svglint.py")] + svgs, text=True)
    return r.returncode == 0

def export_png(svg, png, width):
    inkscape = shutil.which("inkscape")
    if inkscape is None:
        raise SystemExit("Inkscape is needed for the PNG export (apt install inkscape)")
    run([inkscape, svg, "--export-type=png", f"--export-filename={png}", f"--export-width={width}",
         "--export-background=#ffffff", "--export-background-opacity=1"])
    try:
        from PIL import Image
        im = Image.open(png)
        im.save(png, "PNG", optimize=True)
    except ImportError:
        pass
    return png

def main():
    parser = argparse.ArgumentParser(description="Build the LiteX wiki diagrams.")
    parser.add_argument("--only", help="Build this diagram only.")
    parser.add_argument("--check", action="store_true", help="Regenerate to a temporary directory and compare with the committed SVGs.")
    parser.add_argument("--png", action="store_true", help="Also export PNGs to doc/diagrams/build/ (Inkscape).")
    args = parser.parse_args()
    names = [args.only] if args.only else list(DIAGRAMS)
    for n in names:
        if n not in DIAGRAMS:
            raise SystemExit(f"unknown diagram {n}, add it to DIAGRAMS in build.py")

    if args.check:
        ok = True
        with tempfile.TemporaryDirectory() as tmp:
            svgs = []
            for n in names:
                svg = generate(n, tmp)
                committed = os.path.join(IMAGES, f"{n}.svg")
                if not os.path.exists(committed):
                    print(f"{n}: {committed} is missing, run build.py")
                    ok = False
                elif not filecmp.cmp(svg, committed, shallow=False):
                    print(f"{n}: {committed} differs from the output of {n}.py, run build.py")
                    ok = False
                svgs.append(svg)
            ok = lint(svgs) and ok
        print("diagrams: OK" if ok else "diagrams: FAILED")
        sys.exit(0 if ok else 1)

    os.makedirs(IMAGES, exist_ok=True)
    svgs = [generate(n, IMAGES) for n in names]
    ok = lint(svgs)
    if args.png:
        os.makedirs(PNGS, exist_ok=True)
        for n in names:
            png = export_png(os.path.join(IMAGES, f"{n}.svg"), os.path.join(PNGS, f"{n}.png"), DIAGRAMS[n])
            print(png, os.path.getsize(png)//1024, "KB")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
