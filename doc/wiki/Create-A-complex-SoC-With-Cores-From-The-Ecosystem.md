# Create a complex SoC with cores from the ecosystem

The [minimal SoC](Create-A-minimal-SoC.md) is a CPU, memories and a UART; a *complex* SoC adds
the cores of the [ecosystem](Cores-Ecosystem.md): a DRAM controller (LiteDRAM), Ethernet
(LiteEth), an SD card (LiteSDCard), a SPI flash (LiteSPI), SATA (LiteSATA), PCIe (LitePCIe),
video... Each one is a PHY for the board's chips plus one `add_*` call, and each one brings its
BIOS commands, its boot method, its software library and its Linux driver. This page builds the
Linux-capable SoC of the Digilent Arty A7 step by step; the LiteX-Boards targets do the same for
their boards.

![A complex LiteX SoC](images/litex-complex-soc.svg)

## The target

The full version is `litex_boards/targets/digilent_arty.py`; this is its skeleton with the
ecosystem cores:

```python
from litex.soc.cores.clock import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *

from litedram.modules import MT41K128M16
from litedram.phy import s7ddrphy
from liteeth.phy.mii import LiteEthPHYMII

class BaseSoC(SoCCore):
    def __init__(self, sys_clk_freq=100e6, with_ethernet=False, with_etherbone=False, eth_ip="192.168.1.50",
                 with_spi_flash=False, **kwargs):
        platform = digilent_arty.Platform()

        # CRG: sys, sys4x, sys4x_dqs and idelay clocks for the DDR3, 25 MHz for the Ethernet PHY.
        self.crg = _CRG(platform, sys_clk_freq, with_dram=(kwargs.get("integrated_main_ram_size", 0) == 0))

        SoCCore.__init__(self, platform, sys_clk_freq, ident="LiteX SoC on Arty A7", **kwargs)

        # DDR3 SDRAM: LiteDRAM ----------------------------------------------------------------------
        if not self.integrated_main_ram_size:
            self.ddrphy = s7ddrphy.A7DDRPHY(platform.request("ddram"),
                memtype      = "DDR3",
                nphases      = 4,
                sys_clk_freq = sys_clk_freq)
            self.add_sdram("sdram",
                phy           = self.ddrphy,
                module        = MT41K128M16(sys_clk_freq, "1:4"),
                l2_cache_size = kwargs.get("l2_size", 8192))

        # Ethernet / Etherbone: LiteEth -------------------------------------------------------------
        if with_ethernet or with_etherbone:
            self.ethphy = LiteEthPHYMII(
                clock_pads = self.platform.request("eth_clocks"),
                pads       = self.platform.request("eth"))
            if with_etherbone:
                self.add_etherbone(phy=self.ethphy, ip_address=eth_ip, with_ethmac=with_ethernet)
            elif with_ethernet:
                self.add_ethernet(phy=self.ethphy, local_ip=eth_ip)

        # SPI Flash: LiteSPI ----------------------------------------------------------------------
        if with_spi_flash:
            from litespi.modules import S25FL128L
            from litespi.opcodes import SpiNorFlashOpCodes as Codes
            self.add_spi_flash(mode="4x", module=S25FL128L(Codes.READ_1_1_4), rate="1:2", with_master=True)

# main(): ... soc.add_sdcard() with --with-sdcard, soc.add_spi_sdcard() with --with-spi-sdcard ...
```

```sh
python3 -m litex_boards.targets.digilent_arty --cpu-type=vexriscv --cpu-variant=linux \
    --with-ethernet --with-sdcard --with-spi-flash --with-xadc --build --load
```

What each core adds, from the log of that build (`--build --no-compile` shows it in seconds):

```
Bus Regions: (8)
rom                 : Origin: 0x00000000, Size: 0x00020000, Mode:  RX, Cached:  True, Linker: False
spiflash            : Origin: 0x01000000, Size: 0x01000000, Mode:  RX, Cached:  True, Linker: False
sram                : Origin: 0x10000000, Size: 0x00002000, Mode: RWX, Cached:  True, Linker: False
main_ram            : Origin: 0x40000000, Size: 0x10000000, Mode: RWX, Cached:  True, Linker: False
ethmac              : Origin: 0x80000000, Size: 0x00002000, Mode:  RW, Cached: False, Linker:  True
ethmac_rx           : Origin: 0x80000000, Size: 0x00001000, Mode:   R, Cached: False, Linker: False
ethmac_tx           : Origin: 0x80001000, Size: 0x00001000, Mode:  RW, Cached: False, Linker: False
csr                 : Origin: 0xf0000000, Size: 0x00010000, Mode:  RW, Cached: False, Linker: False
Bus Masters: (4)
- cpu_bus0          : rw
- cpu_bus1          : rw
- sdcard_block2mem  : w
- sdcard_mem2block  : r
CSR Locations: (12)
- ctrl, ddrphy, ethmac, ethphy, identifier_mem, leds, sdcard, sdram, spiflash, timer0, uart, xadc
IRQ Locations: (4)
- uart : 0, timer0 : 1, ethmac : 2, sdcard : 3
```

## The cores, one by one

### DRAM: LiteDRAM

- **Gateware**: the PHY for the FPGA family and memory type (`s7ddrphy.A7DDRPHY`/`K7DDRPHY`
  DDR3 on 7-Series, `usddrphy.USDDRPHY`/`USPDDRPHY` DDR3/DDR4 on UltraScale(+),
  `ecp5ddrphy.ECP5DDRPHY` on ECP5, `gw2ddrphy.GW2DDRPHY` on Gowin, `gensdrphy.GENSDRPHY` for SDR
  SDRAM anywhere, the `s6ddrphy` on Spartan-6, the LPDDR4 PHYs...), the module of the chip
  (`litedram.modules`, with its timings; a new chip is a few lines from its datasheet), and
  `add_sdram()`: the controller, the `main_ram` region, the L2 cache in front of the main bus
  (`--l2-size`), direct crossbar ports for the CPUs that have memory buses (VexRiscv-SMP,
  NaxRiscv, VexiiRiscv, Rocket), `sdram_phy.h` with the calibration parameters. The CRG must
  provide the clocks the PHY declares (`sys4x`, `sys4x_dqs`, `idelay` on 7-Series).
- **BIOS**: calibrates the DRAM at boot (`Initializing SDRAM`, read/write leveling on DDR3/4),
  runs the memtest and the memspeed, and offers `sdram_init`, `sdram_cal`, `sdram_test`,
  `sdram_bist`, `sdram_spd`... Linux and the applications get the `main_ram` region; a DMA
  (`WishboneDMAReader/Writer`, the LiteDRAM native ports) reaches it without the CPU.
- **Options**: `--integrated-main-ram-size` replaces the DRAM by block RAM (no PHY), useful on
  small boards and in simulation; `with_bist=True` adds a hardware generator/checker.

### Ethernet: LiteEth

- **Gateware**: the PHY for the interface (`LiteEthPHYMII`, `LiteEthPHYRMII`, `LiteEthPHYGMII`,
  `LiteEthPHYRGMII` per family in `liteeth.phy`, `LiteEthPHY1000BaseX`/SGMII on transceivers,
  `LiteEthPHYXGMII`...) and `add_ethernet(phy, local_ip, remote_ip, nrxslots, ntxslots,
  with_timestamp, with_dhcp)`: the MAC with its RX/TX slots (`ethmac` region, uncached, 2 + 2
  slots of 2 KiB), the interrupt, the `LOCALIP`/`REMOTEIP`/`MACADDR` constants. `add_etherbone(phy,
  ip_address, mac_address, udp_port)` instead (or in addition, `with_ethmac=True` shares the PHY)
  gives the host a [bridge](Host-Bridges.md) with the hardware UDP/IP stack.
- **BIOS**: `netboot` (TFTP, `boot.json`/`boot.bin`), `ping`, `eth_dhcp`, `eth_local_ip`,
  `mdio_*`; Linux gets the `litex_liteeth` driver through the device tree.
- **Options**: `--eth-ip`, `--remote-ip`, `--eth-dhcp`/`--eth-dynamic-ip`, `--with-ethernet`
  and `--with-etherbone` are mutually exclusive on the targets unless the target shares the PHY.

### Storage: LiteSDCard, SPI SD card, LiteSATA

- `add_sdcard()`: the 4-bit SD/eMMC controller with its DMAs (`sdcard_block2mem`,
  `sdcard_mem2block` bus masters), BIST, interrupt; `add_spi_sdcard()`: the bit-banged SPI
  mode for boards without the data pins (slow, no DMA). **BIOS**: `sdcardboot` (FAT, `boot.json`),
  `sdcard_init`, `sdcard_read`/`sdcard_write`; Linux: `litex_mmc`.
- `add_sata(phy=LiteSATAPHY(...), mode="read+write", with_bist=True)`: the SATA controller with
  its `sector2mem`/`mem2sector` DMAs, on the transceivers (7-Series GTP/GTX, UltraScale(+),
  ECP5). **BIOS**: `sataboot`, `sata_init`, `sata_read`/`sata_write`, `sata_rwtest`.

### Flash: LiteSPI

- `add_spi_flash(mode="4x", module=S25FL128L(Codes.READ_1_1_4), rate="1:2", with_master=True)`:
  the memory-mapped flash (`spiflash` region, execute in place, the BIOS can even live there
  with `--cpu-reset-address` at a flash offset) and the master for erase/program
  (`with_master`), the `SPIFLASH_*` constants and `FLASH_BOOT_ADDRESS` for the `flashboot`.
  The module and the read opcode come from the datasheet (`litespi.modules` has many).
- **BIOS**: `flashboot`, `flash_write`, `flash_erase_range`, `flash_from_sdcard`.

### Video

- `add_video_framebuffer(phy, timings="800x600@60Hz", format="rgb888")`: a framebuffer in main
  RAM read by DMA, the timings generator, and a PHY for the output (`VideoVGAPHY`,
  `VideoDVIPHY`, `VideoHDMIPHY`, `VideoS7HDMIPHY`, `VideoGowinHDMIPHY`...); `add_video_terminal`
  shows the console on the screen, `add_video_colorbars` a test pattern; the boards with HDMI
  have `--with-video-framebuffer`/`--with-video-terminal`. Linux gets a `simple-framebuffer`
  node ([Cores](Cores.md#video-and-imaging)).

### PCIe: LitePCIe

`add_pcie(phy=S7PCIEPHY(...), ndmas=1)`: the endpoint, the host [bridge](Host-Bridges.md) to the
whole SoC bus, the DMAs and MSI, the Linux driver and user tools: [Create a PCIe SoC](Create-A-PCIe-SoC.md).

### The small ones

`--with-xadc`/`--with-dna` (Xilinx), `--with-buttons`, `--with-switches`, `--with-pmod-gpio`,
`--with-can`, `--with-i2c`, `--with-spi`, USB (`--uart-name=usb_acm`), the watchdog, the
`--pmod pmodd=sdcard` extensions: the [in-tree cores](Cores.md), one line each.

## From the SoC to Linux

With a DRAM, Ethernet or an SD card and a `linux`-capable CPU, the SoC runs Linux:
`litex_json2dts_linux build/<board>/csr.json > soc.dts` generates the device tree from the
same description (the UART, the Ethernet MAC, the SD card, the SPI flash, the framebuffer, the
GPIOs and I2C get their nodes), and [Linux-on-LiteX-VexRiscv](Run-Linux-On-Your-SoC.md) packages
the kernel, OpenSBI, Buildroot and the boot images for the LiteX-Boards targets. Zephyr,
FreeRTOS and MicroPython use the same headers ([OSes ecosystem](OSes-Ecosystem.md)).

## Checking as you go

- `--build --no-compile`: the map, the CSRs and the interrupts in seconds; `csr.csv` for the
  host tools.
- The BIOS tests every core at boot (DRAM memtest) or on request (`sdcard_init`, `ping`,
  `flash_*`); `litex_cli --regs --filter sdram` reads the calibration registers; `--with-uartbone`
  gives the host the bus while the CPU runs.
- [LiteScope](Use-LiteScope-To-Debug-A-SoC.md) on the signals of a core that misbehaves, in
  [simulation](SoC-Simulator.md) first: `litex_sim --with-sdram --with-ethernet --with-sdcard
  --with-spi-flash` has models for all of them.
