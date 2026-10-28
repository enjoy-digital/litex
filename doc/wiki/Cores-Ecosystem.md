Around LiteX, a family of cores covers what an FPGA system needs: DRAM, Ethernet, PCIe, NVMe,
SATA, SD card, SerDes links, JESD204, SPI, I2C, DSP and a logic analyzer. Each one is its own
repository, written with the same conventions ([streams](Streams.md), [CSRs](CSR-Bus.md), the
[portable layering](LiteX-Approach.md)), tested in CI and used in real systems
([Projects](Projects.md)). You get them with `litex_setup.py` and add them to a SoC in one
call (`add_sdram`, `add_ethernet`, `add_pcie`, `add_sata`, `add_sdcard`, `add_spi_flash`...);
most also ship a standalone generator for designs that are not LiteX SoCs
([Export to Verilog](Export-To-Verilog.md)).

![The LiteX ecosystem](images/litex-ecosystem-map.svg)

*The framework in the middle, the cores around it, the CPUs, the boards, the software and the
host tools.*

```sh
./litex_setup.py --init --install --config=standard   # clones and installs every core below
python3 -c "import litedram, liteeth, litepcie, litescope; print('ok')"
```

## The cores

Pick the core from the first column; the second says what it covers, the third where it has
run.

| Core | What it does | Hardware |
| --- | --- | --- |
| [LiteDRAM](https://github.com/enjoy-digital/litedram) | SDRAM, DDR to DDR4, LPDDR4/5, RPC; a crossbar with native, AXI and Wishbone ports; DMA, BIST, ECC | Xilinx S6, 7-Series, UltraScale(+); Lattice ECP5, Nexus; Gowin GW2A, GW5; generic SDRAM PHY |
| [LiteEth](https://github.com/enjoy-digital/liteeth) | 10M to 100G: MII to RGMII, SGMII, 1000BASE-X, XGMII, 25GBASE-R, CMAC; MAC, ARP, IP, UDP, DHCP, PTP. | Xilinx S6 to UltraScale+; Lattice ECP5; Efinix; Gowin GW5; Intel Agilex; generic |
| [LitePCIe](https://github.com/enjoy-digital/litepcie) | Gen1 to Gen3, x1 to x16; TLP, MSI and MSI-X, scatter-gather DMA, MMAP bridge, PTM; a Linux driver. | Xilinx 7-Series (Gen2 x8), UltraScale(+) (Gen3 x16); Intel Cyclone V (Gen2 x4) |
| [LiteNVMe](https://github.com/enjoy-digital/litenvme) | An NVMe host on a LitePCIe root port: identify, I/O queues, a hardware I/O engine, AXI-Stream data. | Xilinx UltraScale+ (Gen3 x4, about 2.7 GB/s) |
| [LiteSATA](https://github.com/enjoy-digital/litesata) | Gen1 to Gen3, 48-bit LBA, crossbar, BIST, striping and mirroring. | Xilinx Artix-7 GTP, Kintex-7 GTX, UltraScale(+) GTH/GTY; Lattice ECP5 (Gen2) |
| [LiteSDCard](https://github.com/enjoy-digital/litesdcard) | SD, SDHC, SDXC and eMMC, single and multi-block, DMAs, BIST; about 55 MB/s at 125 MHz. | Generic PHY |
| [LiteICLink](https://github.com/enjoy-digital/liteiclink) | Inter-chip links: SerWB (Wishbone over a few pairs) and the SerDes wrappers with PLL, 8b10b, PRBS. | Xilinx 7-Series GTP/GTX/GTH, UltraScale(+) GTH/GTY; Lattice ECP5; Efinix |
| [LiteJESD204](https://github.com/enjoy-digital/litejesd204) | JESD204B (8b10b) and JESD204C (64b66b), shared transport layer, LMFC/LEMC, SYSREF. | Xilinx 7-Series and UltraScale(+) transceivers, through LiteICLink |
| [LiteSPI](https://github.com/litex-hub/litespi) | Single to octal SPI, memory-mapped flash reads, dynamic clock, calibration, a flash model. | Generic |
| [LiteI2C](https://github.com/litex-hub/litei2c) | I2C standard, fast and fast+ modes, crossbar, CSR access; built like LiteSPI. | Generic |
| [LiteScope](https://github.com/enjoy-digital/litescope) | The embedded logic analyzer: triggers, subsampling, RLE, BRAM storage, VCD, sigrok and CSV output. | Generic |
| [LiteDSP](https://github.com/enjoy-digital/litedsp) | RF and DSP blocks (work in progress): mixing, filters, FFT, FEC, OFDM, motor control, audio, radar. | Generic, pure HDL |

The standalone generators: `litedram_gen`, `liteeth_gen`, `litepcie_gen`, `litenvme_gen`,
`litesata_gen`, `litesdcard_gen`, `litespi_gen`, `litedsp_gen` (and `litedsp_flow`); LiteICLink,
LiteJESD204, LiteI2C and LiteScope are used inside a design.

CI, on every push:
[![LiteDRAM](https://github.com/enjoy-digital/litedram/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litedram/actions)
[![LiteEth](https://github.com/enjoy-digital/liteeth/workflows/ci/badge.svg)](https://github.com/enjoy-digital/liteeth/actions)
[![LitePCIe](https://github.com/enjoy-digital/litepcie/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litepcie/actions)
[![LiteNVMe](https://github.com/enjoy-digital/litenvme/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litenvme/actions)
[![LiteSATA](https://github.com/enjoy-digital/litesata/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litesata/actions)
[![LiteSDCard](https://github.com/enjoy-digital/litesdcard/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litesdcard/actions)
[![LiteICLink](https://github.com/enjoy-digital/liteiclink/workflows/ci/badge.svg)](https://github.com/enjoy-digital/liteiclink/actions)
[![LiteJESD204](https://github.com/enjoy-digital/litejesd204/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litejesd204/actions)
[![LiteSPI](https://github.com/litex-hub/litespi/workflows/ci/badge.svg)](https://github.com/litex-hub/litespi/actions)
[![LiteI2C](https://github.com/litex-hub/litei2c/workflows/ci/badge.svg)](https://github.com/litex-hub/litei2c/actions)
[![LiteScope](https://github.com/enjoy-digital/litescope/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litescope/actions)
[![LiteDSP](https://github.com/enjoy-digital/litedsp/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litedsp/actions)
[![LiteX-Boards](https://github.com/litex-hub/litex-boards/workflows/ci/badge.svg)](https://github.com/litex-hub/litex-boards/actions)

## Around them

- **USB 2.0** relies on [LUNA](https://github.com/greatscottgadgets/luna): LiteX integrates its
  CDC-ACM device as the USB console (`--uart-name=usb_acm`), on a ULPI PHY or on LiteX's own
  soft USB2 PHY (`litex/soc/cores/usb2_phy/`, full and high speed in the fabric);
  [USB3-PIPE](https://github.com/enjoy-digital/usb3_pipe) is a USB 3.0 PHY and device core
  without external chip.
- **The in-tree cores** of LiteX itself, UART, timer, GPIO, SPI, I2C, PWM, video, HyperRAM,
  clocking and about forty others, are on [Cores](Cores.md).
- **The boards** are in [LiteX-Boards](https://github.com/litex-hub/litex-boards): platform and
  target files for 200+ boards from 9 FPGA vendors, the starting point for yours
  ([Add a new board](Add-A-New-Board.md)).

## Next

- [Create a complex SoC](Create-A-Complex-SoC.md): DRAM, Ethernet, PCIe and SATA in one target.
- [Cores](Cores.md): the cores inside LiteX itself.
- [Export to Verilog](Export-To-Verilog.md): a core of the ecosystem in a design that is not LiteX.
- [Projects](Projects.md): where these cores come from and run.
