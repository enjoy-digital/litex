The SoC builder is the part of LiteX that turns a Python description into a complete SoC: it
allocates the address map, connects the bus masters and slaves through the interconnect,
collects the control/status registers of every core, assigns the interrupts, generates the
constants the software needs and hands the result to the Builder, which generates the gateware
and the software support. It lives in `litex/soc/integration/soc.py` (the `SoC`, `LiteXSoC`,
`SoCCore` and `SoCMini` classes) and `builder.py` (the `Builder`).

![Anatomy of a LiteX SoC](images/litex-soc-architecture.svg)

## A target in 40 lines

A target instantiates a platform, a clock/reset generator and a `SoCCore`, then adds what it
needs with the `add_*` helpers or by instantiating cores. This is the pattern of every target in
[LiteX-Boards](https://github.com/litex-hub/litex-boards):

```python
#!/usr/bin/env python3
from migen import *
from litex.gen import *

from litex_boards.platforms import digilent_arty

from litex.soc.cores.clock import S7PLL
from litex.soc.cores.led import LedChaser
from litex.soc.integration.soc_core import SoCCore
from litex.soc.integration.builder import Builder

# CRG ----------------------------------------------------------------------------------------------

class _CRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq):
        self.cd_sys = ClockDomain()
        self.pll = pll = S7PLL(speedgrade=-1)
        pll.register_clkin(platform.request("clk100"), 100e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    def __init__(self, sys_clk_freq=100e6, with_led_chaser=True, **kwargs):
        platform = digilent_arty.Platform()
        self.crg = _CRG(platform, sys_clk_freq)
        SoCCore.__init__(self, platform, sys_clk_freq, ident="LiteX SoC on Arty A7", **kwargs)
        if with_led_chaser:
            self.leds = LedChaser(pads=platform.request_all("user_led"), sys_clk_freq=sys_clk_freq)

# Build --------------------------------------------------------------------------------------------

def main():
    from litex.build.parser import LiteXArgumentParser
    parser = LiteXArgumentParser(platform=digilent_arty.Platform, description="LiteX SoC on Arty A7.")
    parser.add_target_argument("--sys-clk-freq", default=100e6, type=float, help="System clock frequency.")
    args = parser.parse_args()

    soc = BaseSoC(sys_clk_freq=args.sys_clk_freq, **parser.soc_argdict)
    builder = Builder(soc, **parser.builder_argdict)
    if args.build:
        builder.build(**parser.toolchain_argdict)
    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(builder.get_bitstream_filename(mode="sram"))

if __name__ == "__main__":
    main()
```

`python3 target.py --build --load` builds and loads it; `--help` lists the options the parser
adds for the SoC, the Builder, the toolchain and the CPU. The `**kwargs`/`soc_argdict` pair is
how `--cpu-type`, `--integrated-main-ram-size`, `--uart-name`, ... reach `SoCCore`.
[Create a minimal SoC](Create-A-minimal-SoC.md) walks through it step by step.

## The classes

| Class | Role |
| --- | --- |
| `SoC` | The base: the bus handler (`self.bus`), the CSR handler (`self.csr`), the IRQ handler (`self.irq`), the constants and the regions; `add_ram`/`add_rom`, `add_csr_bridge`, `add_cpu`, `add_timer`, `add_watchdog`, `add_constant`/`add_config`; the finalization that builds the interconnect and exports everything. |
| `LiteXSoC(SoC)` | Adds the helpers for the LiteX cores and the ecosystem: `add_uart`, `add_uartbone`, `add_jtagbone`, `add_etherbone`, `add_ethernet`, `add_sdram`, `add_hyperram`, `add_spi_flash`, `add_spi_ram`, `add_spi_master`, `add_i2c_master`, `add_spi_sdcard`, `add_sdcard`, `add_sata`, `add_pcie`, `add_video_*`, `add_cpu_jtag_debug`. |
| `SoCCore(LiteXSoC)` | The usual base class of a target: from its constructor arguments it adds, in this order, the controller (`ctrl`), the CPU, the ROM (with the BIOS), the SRAM, the main RAM, the identifier, the UARTBone, the UART, the JTAGBone, the CPU JTAG debug, the timer and the watchdog. Its `mem_map` gives the default origins. |
| `SoCMini(SoCCore)` | The same with no CPU, no UART, no timer and no SRAM by default: for designs controlled from the host through a bridge, or cores exported to another flow. |

`SoCCore(platform, sys_clk_freq, ...)` arguments and their defaults, which are also the
`--`-options of the targets:

| Argument | Default | Option | Meaning |
| --- | --- | --- | --- |
| `bus_standard`, `bus_data_width`, `bus_address_width`, `bus_addressing`, `bus_timeout`, `bus_bursting`, `bus_interconnect`, `bus_arbiter`, `bus_low_latency` | `wishbone`, 32, 32, word (byte for AXI), 1e6 cycles, off, `shared`, `default`, off | `--bus-*` | The main bus ([below](#the-bus-and-its-handler)). |
| `cpu_type`, `cpu_variant`, `cpu_reset_address`, `cpu_cfu` | `vexriscv`, the CPU's default (`standard`), the `rom` origin, none | `--cpu-type`, `--cpu-variant`, `--cpu-reset-address`, `--cpu-cfu` | The CPU ([CPUs](CPUs.md)). `--cpu-type=None` for a SoC without CPU. |
| `integrated_rom_size`, `integrated_rom_init`, `integrated_rom_mode` | 0x20000 (auto-sized to the BIOS), none, `rx` | `--integrated-rom-size`, `--integrated-rom-init` | The ROM in block RAM holding the BIOS (or your firmware with `--integrated-rom-init`). |
| `integrated_sram_size`, `integrated_main_ram_size` | 0x2000, 0 | `--integrated-sram-size`, `--integrated-main-ram-size` | SRAM (stack, BIOS data) and main RAM in block RAM; a DRAM comes from `add_sdram` instead. |
| `csr_data_width`, `csr_address_width`, `csr_paging`, `csr_ordering` | 32, 14, 0x800, `big` | `--csr-*` | The CSR bus ([CSR-Bus](CSR-Bus.md)). |
| `ident`, `ident_version` | "", `False` | `--ident`, `--no-ident-version` | The identifier string (`litex_cli --ident`, the BIOS banner), with the build time. |
| `with_uart`, `uart_name`, `uart_baudrate`, `uart_fifo_depth` | `True`, `serial`, 115200, 16 | `--no-uart`, `--uart-name`, `--uart-baudrate`, `--uart-fifo-depth` | The console: `serial`, `crossover` (through a bridge), `crossover+uartbone`, `jtag_uart`, `usb_acm`, `sim`, `stub`, `stream`. |
| `with_uartbone`, `with_jtagbone`, `jtagbone_chain` | off, off, 1 | `--with-uartbone`, `--with-jtagbone`, `--jtagbone-chain` | [Host bridges](Host-Bridges.md). |
| `with_cpu_jtag_debug`, `cpu_jtag_debug_transport`, `cpu_jtag_debug_chain` | off, `user`, 4 | `--with-cpu-jtag-debug`, `--cpu-jtag-debug-transport`, `--cpu-jtag-debug-chain` | CPU debug over JTAG ([JTAG/GDB](JTAG-GDB-Debugging-with-VexRiscv-SMP-NaxRiscv-VexiiRiscv-CPUs.md)). |
| `with_timer`, `timer_uptime`, `with_ctrl`, `with_watchdog` | on, off, on, off | `--no-timer`, `--timer-uptime`, `--no-ctrl`, `--with-watchdog` | Timer (required by the BIOS), SoC controller (reset, scratch, bus errors), watchdog. |
| `irq_n_irqs` | 32 | | Number of interrupt lines. |

## The address map

Every memory and peripheral is a *region* with an origin, a size and attributes:
`SoCRegion(origin, size, mode="rw", cached=True, linker=False, decode=True)`; `SoCIORegion` is
the uncached variant for peripherals. The default origins come from `mem_map`, and the CPU
overrides them with its own map when it has constraints (`cpu.mem_map`):

```python
SoCCore.mem_map = {"rom": 0x00000000, "sram": 0x01000000, "main_ram": 0x40000000}
# VexRiscv (litex/soc/cores/cpu/vexriscv/core.py):
mem_map = {"rom": 0x00000000, "sram": 0x10000000, "main_ram": 0x40000000, "csr": 0xf0000000}
```

A target can override an origin before calling `SoCCore.__init__` (`self.mem_map["csr"] = ...`)
or let the handler allocate (`self.bus.alloc_region(name, size)`); the CPU's IO regions (for
example `0x80000000-0xffffffff` on most 32-bit soft CPUs) are where uncached peripherals must
live, which the handler checks. The final map is exported as `mem.h` and `regions.ld` for the
software, `csr.csv`/`csr.json`/`csr.svd` for the tools, and printed in the build log:

```
Bus Regions:
rom      : Origin: 0x00000000, Size: 0x00020000, Mode: RX,  Cached: True,  Linker: False
sram     : Origin: 0x10000000, Size: 0x00002000, Mode: RWX, Cached: True,  Linker: False
main_ram : Origin: 0x40000000, Size: 0x10000000, Mode: RWX, Cached: True,  Linker: False
csr      : Origin: 0xf0000000, Size: 0x00010000, Mode: RW,  Cached: False, Linker: False
```

## The bus and its handler

`self.bus` (`SoCBusHandler`) owns the main bus: one standard (`wishbone`, `axi-lite` or `axi`),
one data width (32 to 512 bits), one address width (32 or 64), word or byte addressing, and an
interconnect built at finalization: a shared bus (one arbiter, one decoder, the default) or a
crossbar (`--bus-interconnect=crossbar`, every master to every slave). It also provides a
timeout that returns an error instead of hanging the SoC when a slave does not answer
(counted in the controller's `bus_errors` register) and optional bursts (`--bus-bursting`).

```python
self.bus.add_master(name="dma", master=my_dma.bus)                          # a new bus master
self.bus.add_slave(name="buf", slave=my_sram.bus, region=SoCRegion(size=0x1000, cached=False))
self.bus.add_slave("ext", ext_bus, region=SoCRegion(origin=0x90000000, size=0x100000), clock_domain="eth")
```

A master or a slave of another standard or width is adapted automatically (`add_adapter`):
width converters, word/byte addressing, and the Wishbone/AXI-Lite/AXI bridges in both
directions; a `clock_domain` adds a clock domain crossing. This is why a Wishbone CPU, an AXI
DMA from a vendor IP and a 512-bit LiteDRAM port can share one SoC. The details of each bus are
on the [Wishbone](Wishbone-Bus.md) and [AXI](AXI-Bus.md) pages.

## CSRs and interrupts

`self.csr` (`SoCCSRHandler`) allocates one *location* (a page of `csr_paging` bytes, 0x800 by
default) per core with CSRs, in the `csr` region reached through the CSR bridge
(`add_csr_bridge`, automatic). Cores are found by name: any submodule with `CSRStorage`/`CSRStatus`
attributes gets a location, in declaration order, or at a fixed index with
`self.csr.add("uart", n=2)` (for a stable map across builds). 32 locations at the default width
and paging; `--csr-address-width=15` doubles them. [CSR-Bus](CSR-Bus.md) explains the bus and
the generated accessors.

`self.irq` (`SoCIRQHandler`) assigns the interrupt lines: `self.irq.add("uart")` for a core
with an `EventManager` (the helpers do it), or `self.irq.add("mycore", n=5)` for a fixed line.
The numbers are exported as `<NAME>_INTERRUPT` in `soc.h`; the BIOS and the OS device trees
use them.

## The `add_*` API

| Helper | What it adds |
| --- | --- |
| `add_rom(name, origin, size, contents, mode="rx")`, `add_ram(name, origin, size, contents, mode="rwx")` | A block RAM on the bus (`wishbone.SRAM`, `AXILiteSRAM` or `AXISRAM`), its region, and `CONFIG_<NAME>_INIT` when it has contents. |
| `add_sdram(name, phy, module, origin, size, l2_cache_size=8192, with_bist, ...)` | The LiteDRAM controller for the given PHY and module, the `main_ram` region, an L2 cache between the bus and the DRAM, the direct ports for the CPUs that have memory buses (VexRiscv-SMP, NaxRiscv, Rocket...), `sdram_phy.h` for the BIOS calibration. |
| `add_hyperram(name, pads, origin, size, ...)`, `add_spi_flash(name, mode="4x", clk_freq, module, ...)`, `add_spi_ram(...)` | HyperRAM, LiteSPI memory-mapped flash (`spiflash` region, XIP, `FLASH_BOOT_ADDRESS` for the BIOS) and SPI RAM. |
| `add_cpu(name, variant, reset_address, cfu)` | The CPU: its buses as masters, its IO regions, its interrupts, the reset address (the `rom` origin by default), the DMA bus for coherent DMAs, the `CPU_*` constants. [CPUs](CPUs.md). |
| `add_controller()`, `add_identifier(identifier)`, `add_timer()`, `add_watchdog(width, reset_delay)` | The SoC controller (reset, scratch, bus error counter), the identifier string, the timer (required by the BIOS: delays, boot timeouts), the watchdog. |
| `add_uart(name, uart_name, baudrate, fifo_depth)`, `add_uartbone(...)`, `add_jtagbone(chain)` | The console UART (IRQ or `UART_POLLING`) and the [host bridges](Host-Bridges.md). |
| `add_ethernet(name, phy, nrxslots, ntxslots, with_timestamp, local_ip, remote_ip, dynamic_ip, with_dhcp)`, `add_etherbone(name, phy, ip_address, mac_address, udp_port, with_ethmac)` | LiteEth: the MAC for the CPU (BIOS netboot, Linux) and/or the Etherbone bridge; both can share one PHY. |
| `add_pcie(name, phy, ndmas, with_dma_buffering, ...)` | LitePCIe: the endpoint, the MMAP bridge (host access to the bus), the DMAs and MSI; constants for the driver. |
| `add_sata(name, phy, mode, with_bist)`, `add_sdcard(name)`, `add_spi_sdcard(name, spi_clk_freq)` | LiteSATA and LiteSDCard with their DMAs (`sector2mem`/`block2mem` masters), or the bit-banged SPI SD card for small FPGAs. |
| `add_i2c_master(name, pads)`, `add_spi_master(name, pads, data_width, spi_clk_freq)` | I2C and SPI masters with their interrupts and constants. |
| `add_video_colorbars(name, phy, timings, clock_domain)`, `add_video_terminal(...)`, `add_video_framebuffer(name, phy, timings, format, base)` | Video out: test pattern, text terminal on the UART stream, framebuffer in main RAM (with its DMA and `VIDEO_FRAMEBUFFER_*` constants). |
| `add_cpu_jtag_debug(chain, transport)` | The CPU debug TAP through a USER chain or through CSRs (`litex_jtag`). |
| `add_constant(name, value)`, `add_config(name, value)` | A `#define` in `soc.h` (`CONFIG_` prefix with `add_config`): parameters for the BIOS and the firmware. |
| `add_soc_reset_request(name, reset)` | A signal that resets the SoC (watchdog, PCIe link down...). |

The helpers follow a convention: `name` is the CSR/IRQ name and the prefix of the constants;
the module is available as `self.<name>` afterwards (`self.sdram`, `self.ethphy`,
`self.ethmac`, `self.pcie_phy`...), so a target can refine it.

## The Builder

`Builder(soc, output_dir="build/<platform>", ...)` then `builder.build()`:

![The LiteX build flow](images/litex-build-flow.svg)

1. Finalizes the SoC: regions, CSR locations, interrupts, constants, the interconnect.
2. Generates the software support in `software/include/generated/`: `csr.h` (register
   accessors), `soc.h` (constants), `mem.h` (regions), `git.h`, `variables.mak`, the linker
   scripts `output_format.ld` and `regions.ld`, `sdram_phy.h` with a DRAM, and `csr.csv`,
   `csr.json` (always), `csr.svd` and `memory.x` on request.
3. Builds the software packages with `make` (meson >= 0.59 is required by picolibc): libc,
   `libbase`, `libcompiler_rt`, `libfatfs`, `liblitespi`, `liblitedram`, `libliteeth`,
   `liblitesdcard`, `liblitesata` and the [BIOS](BIOS.md), then loads `bios.bin` into the
   ROM (resized to fit unless `--no-integrated-rom-auto-size`).
4. Generates the gateware (Verilog and constraints) and runs the toolchain
   ([Build-Backends](Build-Backends.md)) when `compile_gateware` is set.
5. With `--doc`, generates the Sphinx documentation ([SoC-Documentation](SoC-Documentation.md)).

Loading and flashing are done by the target after the build (`--load`, `--flash`), with the
programmer of the platform. The options, available on every target:

| Option | Meaning |
| --- | --- |
| `--build`, `--load`, `--flash`, `--toolchain` | Build, load, flash; the toolchain among those of the platform (first one by default). |
| `--output-dir`, `--gateware-dir`, `--software-dir`, `--include-dir`, `--generated-dir` | Where things go (default `build/<platform>/{gateware,software}`). |
| `--no-compile`, `--no-compile-gateware`, `--no-compile-software` | Generate without running the toolchain and/or `make`: `--build --no-compile-gateware` gives the software support without an FPGA toolchain. |
| `--soc-csv`, `--soc-json`, `--soc-svd`, `--memory-x`, `--doc`, `--hierarchical-verilog` | Extra outputs (`--csr-*` are the old names of the first three). |
| `--build-backend {litex,edalize}`, `--build-log`, `--no-build-log` | The build backend; the log is `<output-dir>/litex.log` by default. |
| `--bios-lto`, `--bios-format {integer,float,double}`, `--bios-console {full,no-history,no-autocomplete,lite,disable}`, `--bios-no-ansi`, `--bios-stack-margin`, `--libc-mode {minimal,full}`, `--no-integrated-rom-auto-size` | BIOS and libc build options ([BIOS](BIOS.md)). |
| `--build-bundle [PATH]`, `--bundle-*` | Record the inputs of the build in an archive to replay it elsewhere (`litex_build_bundle`, `litex_remote_build`, see [Tools](Tools.md)). |
| `--log-filename`, `--log-level` | Logging. |

`builder.get_bitstream_filename(mode="sram"|"flash")` and `builder.get_bios_filename()` give the
paths of the results. Standalone generation of a SoC without a board (`litex_soc_gen`) and the
export of a SoC as a Verilog core are on [Export your core/SoC to Verilog](Export-Your-Core-SoC-To-Verilog.md).

## Finalization checks worth knowing

- The CPU reset address must fall in a region (the ROM by default); an `--integrated-rom-size 0`
  with a CPU needs `--cpu-reset-address` in the flash or main RAM.
- The BIOS needs the `timer0` CSRs and the `rom` and `sram` regions (`check_bios_requirements`);
  a design with `--no-timer` builds without BIOS (`--integrated-rom-init` for your own code).
- Regions must not overlap and uncached regions must sit in the CPU's IO regions; the handler
  raises a clear error with the conflicting names.
- A peripheral is seen by software only if it has CSRs (a location) or a bus region: a module
  that is not an attribute of the SoC (or added with `add_module`) is invisible.
