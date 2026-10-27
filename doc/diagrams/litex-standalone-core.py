#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-standalone-core.svg: exporting a core or a SoC as a Verilog module for a non-LiteX design,
for the Export-Your-Core-SoC-To-Verilog page.

    python3 doc/diagrams/litex-standalone-core.py   # -> doc/wiki/images/litex-standalone-core.svg
"""

from litex_diagram import *

W, H = 1400, 620

DESC = ("Standalone cores. Left: a YAML configuration (or command-line options) goes into a generator: "
        "liteeth_gen, litedram_gen, litepcie_gen, litesata_gen, litesdcard_gen, litespi_gen, litenvme_gen, "
        "litedsp_gen, usb3_pipe_gen, or litex_soc_gen/litex_periph_gen for a whole SoC. Middle: what comes "
        "out: the Verilog module with its memory init files, the constraints and hard IP scripts, the "
        "software headers and csr.csv, an instantiation template and documentation. Right: your Vivado, "
        "Quartus, Diamond or Yosys project instantiates the module: clock and reset, the pads, an AXI-Lite "
        "or Wishbone control port, AXI-Stream or native data ports, interrupts; the host or your CPU uses "
        "the headers.")

def draw(d):
    # Input.
    d.box(30, 150, 300, 300, fill=KEY, lines=[("Configuration", 17, "bold"), ("YAML: phy, vendor, clk_freq,", 12), ("core, ports, dma_channels, ...", 12), ("or command-line options", 12)])
    d.text(165, 325, "liteeth_gen examples/udp_s7phyrgmii.yml", 11, style="italic")
    d.text(165, 343, "litex_soc_gen --cpu-type=vexriscv --bus-standard=axi-lite", 11, style="italic")
    d.arrow([(300, 225), (360, 225)], thick=True)

    # Generator.
    d.box(360, 60, 700, 420, fill=FPGA, c=22)
    d.text(530, 90, "Generator", 18, weight="bold")
    d.text(530, 108, "a short LiteX target, no board", 12, style="italic")
    gens = [("liteeth_gen", "MAC core or UDP/Etherbone core"), ("litedram_gen", "controller + PHY + calibration CPU"),
            ("litepcie_gen · litenvme_gen", "endpoint, MMAP, DMAs, MSI"), ("litesata_gen · litesdcard_gen · litespi_gen", "storage"),
            ("litedsp_gen · usb3_pipe_gen", "DSP chains, USB3 PHY/device"), ("litex_soc_gen · litex_periph_gen", "a whole SoC with mmap_s / mmap_m ports")]
    y = 125
    for t, s in gens:
        d.box(375, y, 685, y + 42, fill=WHITE, c=8, lines=[(t, 12, "bold"), (s, 11)])
        y += 48
    d.arrow([(700, 225), (760, 225)], thick=True)

    # Outputs.
    d.box(760, 60, 1040, 420, fill=GROUP, c=18)
    d.text(900, 90, "Outputs", 18, weight="bold")
    d.text(900, 108, "build/gateware, build/software", 12, style="italic")
    outs = [("<core>.v", "the module, flattened"), ("*.init", "memory contents ($readmemh)"), (".xdc / .lpf · .tcl", "internal constraints, hard IP"),
            ("csr.h · soc.h · mem.h", "registers for the host / CPU"), ("csr.csv · csr.json", "for the LiteX host tools"), ("<core>_inst.v · <core>.md", "template, documentation")]
    y = 125
    for t, s in outs:
        d.box(775, y, 1025, y + 42, fill=WHITE, c=8, lines=[(t, 12, "bold"), (s, 11)])
        y += 48
    d.arrow([(1040, 225), (1100, 225)], thick=True)

    # Your design.
    d.box(1100, 60, 1370, 420, fill=BOARD, c=18)
    d.text(1235, 90, "Your design", 18, weight="bold")
    d.text(1235, 108, "Vivado · Quartus · Diamond · Yosys", 12, style="italic")
    d.box(1115, 125, 1355, 300, fill=WHITE, lines=[("top.v", 14, "bold"), ("liteeth_core eth (.sys_clock, ...)", 11), ("clk / rst · the pads", 11), ("AXI-Lite or Wishbone control", 11), ("AXI-Stream / native data ports", 11), ("interrupts", 11), ("pin and transceiver constraints", 11)])
    d.box(1115, 315, 1355, 405, fill=WHITE, lines=[("Your software", 14, "bold"), ("host driver or your CPU's firmware", 11), ("#include \"csr.h\"", 11), ("litex_server for LiteScope", 11)])

    d.caption(700, 480, "A LiteX core in a non-LiteX design", "the vendor pieces are resolved by the generator, the interfaces are standard; the board target itself exports its Verilog with --build --no-compile-gateware")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-standalone-core", W, H, "Exporting LiteX cores and SoCs as Verilog modules", DESC)
