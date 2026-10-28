#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-cpu-integration.svg: how a CPU wrapper plugs into a SoC, for the CPUs and Add-A-New-CPU
pages: the core instance inside the wrapper, its buses, interrupts and reset, what it tells the
SoC builder and the Builder.

    python3 doc/diagrams/litex-cpu-integration.py   # -> doc/wiki/images/litex-cpu-integration.svg
"""

from litex_diagram import *

W, H = 1400, 660

DESC = ("A CPU in a LiteX SoC. The wrapper (litex/soc/cores/cpu/<name>/core.py) instantiates the "
        "core (Verilog, VHDL, SpinalHDL, Chisel or Amaranth sources, from a pythondata package or "
        "generated at build time) and exposes it to the SoC builder: the peripheral buses become "
        "masters of the main bus through adapters, the memory buses go straight to the LiteDRAM "
        "crossbar, the DMA bus is a coherent slave port for the DMAs, the interrupt lines come from "
        "the IRQ handler, the reset from the SoC controller, the reset address from the ROM origin. "
        "The wrapper also gives the memory map constraints (io_regions, mem_map) to the SoC builder "
        "and the compiler flags, crt0.S and irq.h to the Builder for the BIOS and the firmware.")

def draw(d):
    rows = [(110, 165), (175, 230), (240, 295), (305, 350), (360, 405)]
    mid  = [(a + b)/2 for a, b in rows]

    # Wrapper.
    d.box(380, 40, 1020, 420, fill=FPGA, c=22)
    d.text(700, 70, "CPU wrapper: litex/soc/cores/cpu/<name>/core.py", 17, weight="bold")
    d.text(700, 90, "class <Name>(CPU): category · family · variants · data_width · gcc_* · io_regions · mem_map", 12, style="italic")
    d.box(760, 110, 1000, 405, fill=KEY, lines=[("The core", 16, "bold"), ("Instance(\"picorv32\", **params)", 12), ("", 8),
                                                 ("Verilog · VHDL · SpinalHDL", 12), ("Chisel · Amaranth", 12), ("", 8),
                                                 ("pythondata-cpu-<name> package,", 12), ("downloaded or generated at build", 12), ("", 8),
                                                 ("add_jtag(): the debug TAP", 12), ("+debug variants", 12)])
    iface = [("periph_buses", "ibus / dbus: Wishbone, AXI"),
             ("memory_buses", "optional, straight to LiteDRAM"),
             ("dma_bus", "optional, coherent slave port"),
             ("interrupt", "Signal(n), reserved_interrupts"),
             ("reset · reset_address", "set_reset_address()")]
    for (y1, y2), (t, s_) in zip(rows, iface):
        d.box(400, y1, 640, y2, lines=[(t, 13, "bold"), (s_, 11)])
        d.arrow([(640, (y1 + y2)/2), (760, (y1 + y2)/2)], double=True)

    # Left: SoC builder, one row per interface.
    d.box(30, 40, 330, 420, fill=GROUP, c=18)
    d.text(180, 70, "SoC builder (add_cpu)", 16, weight="bold")
    d.text(180, 90, "litex/soc/integration/soc.py", 12, style="italic")
    left = [("Main bus", "adapters: standard, width, addressing", WHITE),
            ("LiteDRAM crossbar", "add_sdram connects memory_buses", MEM),
            ("DMAs of the cores", "on the dma_bus when it exists", WHITE),
            ("IRQ handler", "<CORE>_INTERRUPT lines", WHITE),
            ("Controller · address map", "soc_rst | cpu_rst · rom origin · io_regions", WHITE)]
    for (y1, y2), (t, s_, f) in zip(rows, left):
        d.box(45, y1, 315, y2, fill=f, lines=[(t, 13, "bold"), (s_, 11)])
    d.arrow([(315, mid[0]), (400, mid[0])], double=True, thick=True)
    d.arrow([(315, mid[1]), (400, mid[1])], double=True, thick=True)
    d.arrow([(315, mid[2]), (400, mid[2])], double=True, thick=True)
    d.arrow([(315, mid[3]), (400, mid[3])])
    d.arrow([(315, mid[4]), (400, mid[4])])

    # Right: Builder / software.
    d.box(1060, 40, 1370, 420, fill=GROUP, c=18)
    d.text(1215, 70, "Builder: the software", 16, weight="bold")
    d.text(1215, 90, "litex/soc/integration/builder.py", 12, style="italic")
    right = [("gcc_triple · gcc_flags", "-march / -mabi, the compiler to find"),
             ("crt0.S · irq.h · system.h", "start-up, interrupts, caches"),
             ("mem_map · reset address", "regions.ld, CPU_RESET_ADDR"),
             ("BIOS · firmware · OS", "built once for every CPU")]
    for (y1, y2), (t, s_) in zip(rows, right):
        d.box(1075, y1, 1355, y2, lines=[(t, 13, "bold"), (s_, 11)])
    d.arrow([(1020, 170), (1060, 170)], thick=True)

    d.caption(700, 500, "One wrapper, every CPU", "38 soft, hard and emulated CPUs share the same BIOS, software support and SoC integration; --cpu-type / --cpu-variant select them")
    d.text(700, 560, "out-of-tree: a <name>/core.py directory next to your target is found by --cpu-type without changing LiteX", 12, style="italic")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-cpu-integration", W, H, "How a CPU is integrated in a LiteX SoC", DESC)
