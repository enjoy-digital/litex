#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-pcie-soc.svg: a LitePCIe SoC and its host software, for the Create-A-PCIe-SoC page.

    python3 doc/diagrams/litex-pcie-soc.py   # -> doc/wiki/images/litex-pcie-soc.svg
"""

from litex_diagram import *

W, H = 1400, 720

DESC = ("A LiteX PCIe SoC. On the host: the LitePCIe kernel driver (litepcie.ko, one /dev/litepcieN per "
        "DMA channel, liteuart.ko for the console), liblitepcie, litepcie_util/litepcie_test, your "
        "application, and litex_server --pcie for the LiteX tools without the driver. In the FPGA: the "
        "PHY wrapping the vendor hard IP in the pcie clock domain, the endpoint (TLP layer, crossbar), "
        "the MMAP master mapping BAR0 to the SoC bus (CSRs, memories, every core), the DMA channels "
        "(reader and writer with scatter-gather descriptors, buffering, loopback, synchronizer) connected "
        "to the streams of your cores, the MSI interrupts; the SoC around it with an optional CPU, "
        "LiteDRAM, and the cores the design is about.")

def draw(d):
    # Host.
    d.box(30, 40, 430, 600, fill=BOARD, c=22)
    d.text(230, 70, "Host PC (Linux)", 20, weight="bold")
    d.box(50, 95, 410, 165, lines=[("Your application", 15, "bold"), ("liblitepcie: registers, DMA buffers", 12), ("litepcie_test record / play", 12)])
    d.box(50, 180, 410, 250, lines=[("litepcie_util", 15, "bold"), ("info · scratch_test · dma_test", 12), ("flash_write / flash_read / flash_reload", 12)])
    d.box(50, 265, 410, 345, fill=KEY, lines=[("litepcie.ko · liteuart.ko", 15, "bold"), ("/dev/litepcie0..N (one per DMA channel)", 12), ("MMAP and DMA ioctls, MSI, zero-copy mmap", 12), ("/dev/ttyLXU0: the crossover UART", 12)])
    d.box(50, 360, 410, 430, lines=[("litex_server --pcie --pcie-bar=01:00.0", 13, "bold"), ("BAR0 through sysfs, no driver needed", 12), ("litex_cli · LiteScope · litex_term crossover", 12)])
    d.box(50, 445, 410, 505, fill=HARD, lines=[("PCIe root complex", 14, "bold"), ("lspci -vv: LnkSta 5 GT/s x4, BAR0, MSI", 12)])
    d.arrow([(230, 165), (230, 180)], double=True)
    d.arrow([(230, 250), (230, 265)], double=True)
    d.arrow([(230, 345), (230, 360)], double=True, dash=True)
    d.arrow([(230, 430), (230, 445)], double=True)
    d.arrow([(410, 475), (500, 475)], double=True, thick=True)
    d.text(465, 462, "PCIe", 13, weight="bold")
    d.text(465, 492, "Gen2 x4", 12, style="italic")

    # FPGA.
    d.box(500, 40, 1370, 600, fill=FPGA, c=22)
    d.text(935, 70, "FPGA: LiteX SoC with LitePCIe", 20, weight="bold")
    d.box(520, 430, 720, 520, fill=HARD, lines=[("PCIe PHY", 15, "bold"), ("S7PCIEPHY · USPPCIEPHY · ...", 12), ("vendor hard IP, pcie clock domain", 12), ("link status, LTSSM tracer", 12)])
    d.box(760, 430, 960, 520, fill=KEY, lines=[("Endpoint", 15, "bold"), ("TLP packetizer / depacketizer", 12), ("requests, completions", 12), ("crossbar", 12)])
    d.arrow([(720, 475), (760, 475)], double=True, thick=True)
    d.box(1000, 430, 1350, 520, lines=[("MSI", 15, "bold"), ("msi · msi-multi-vector · msi-x", 12), ("DMA events + your interrupts", 12), ("<NAME>_INTERRUPT constants", 12)])
    d.arrow([(960, 475), (1000, 475)])

    d.box(760, 290, 960, 380, fill=KEY, lines=[("MMAP master", 15, "bold"), ("BAR0 -> SoC bus", 12), ("pcie_mmap, bus master", 12)])
    d.box(1000, 290, 1350, 380, fill=KEY, lines=[("DMA channels", 15, "bold"), ("pcie_dma0..N: reader + writer", 12), ("scatter-gather descriptors, buffering", 12), ("loopback · synchronizer · monitor", 12)])
    d.arrow([(860, 430), (860, 380)], double=True, thick=True)
    d.arrow([(1175, 430), (1175, 380)], double=True, thick=True)

    d.box(520, 100, 960, 250, fill=GROUP, c=18)
    d.text(740, 128, "The SoC (optional CPU)", 16, weight="bold")
    d.box(535, 145, 740, 235, lines=[("Main bus + CSRs", 14, "bold"), ("every core visible from the host", 12), ("memories, LiteDRAM", 12), ("CPU + crossover UART, optional", 12)])
    d.box(760, 145, 945, 235, lines=[("LiteDRAM · flash", 14, "bold"), ("DDR for buffering", 12), ("SPI flash: bitstream", 12), ("update over PCIe", 12)])
    d.arrow([(860, 290), (860, 250)], double=True, thick=True)

    d.box(1000, 100, 1350, 250, fill=GROUP, c=18)
    d.text(1175, 128, "Your cores", 16, weight="bold")
    d.box(1015, 145, 1335, 235, lines=[("stream sink / source", 14, "bold"), ("RF samples (LiteX-M2SDR), ADC data", 12), ("(ThunderScope), video, storage, ...", 12), ("at the link rate, no CPU in the path", 12)])
    d.arrow([(1175, 290), (1175, 250)], double=True, thick=True)

    d.caption(700, 650, "The host drives the FPGA: registers through BAR0, data through the DMAs", "add_pcie(phy, ndmas): endpoint, MMAP bridge, DMAs, MSI, the driver and the tools; --driver generates build/<board>/driver/")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-pcie-soc", W, H, "A LiteX PCIe SoC with LitePCIe", DESC)
