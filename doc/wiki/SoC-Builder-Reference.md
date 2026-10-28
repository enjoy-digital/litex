Every argument of `SoCCore`, every `add_*` helper, every option of the Builder, and the checks
run at finalization: the tables behind [SoC builder](SoC-builder.md), from
`litex/soc/integration/soc.py`, `soc_core.py` and `builder.py` as of 2026-10-28. `--help` on
any target prints the live list:

```sh
python3 -m litex_boards.targets.digilent_arty --help      # SoC, Builder, toolchain and CPU options
```

## SoCCore arguments

The options everyone meets; the argument of `SoCCore` has the same name with underscores:

| Option | Default | What it changes |
| --- | --- | --- |
| `--cpu-type`, `--cpu-variant` | `vexriscv`, `standard` | The CPU and its configuration; `--cpu-type=None` for a SoC without CPU. |
| `--cpu-reset-address` | the `rom` origin | Where the CPU starts: the flash or the main RAM when there is no ROM. |
| `--integrated-rom-size`, `--integrated-rom-init` | 0x20000, none | The ROM in block RAM: the BIOS (resized to it), or your firmware. |
| `--integrated-sram-size` | 0x2000 | The SRAM in block RAM: the stack and the data of the BIOS. |
| `--integrated-main-ram-size` | 0 | A main RAM in block RAM; a DRAM comes from `add_sdram` instead. |
| `--uart-name`, `--uart-baudrate` | `serial`, 115200 | The console: `serial`, `crossover`, `crossover+uartbone`, `jtag_uart`, `usb_acm`, `sim`, `stub`. |
| `--with-uartbone`, `--with-jtagbone` | off | A host bridge on the serial port or on the JTAG port. |
| `--bus-standard`, `--bus-data-width` | `wishbone`, 32 | The main bus (`axi-lite`, `axi`) and its width (32 to 512). |
| `--csr-data-width`, `--csr-address-width` | 32, 14 | The CSR bus: bits per slot, size of the `csr` region. |
| `--ident`, `--no-ident-version` | "", with the build time | The identifier string (`litex_cli --ident`, the BIOS banner). |
| `--no-timer`, `--timer-uptime`, `--with-watchdog` | timer on | The timer the BIOS needs, its uptime counter, a watchdog. |
| `--with-cpu-jtag-debug` | off | The CPU debug TAP on a USER chain or through CSRs. |

<details>
<summary>Every argument of SoCCore, with its default</summary>

```python
SoCCore(platform, clk_freq,
    # The main bus.
    bus_standard="wishbone", bus_data_width=32, bus_address_width=32, bus_addressing=None,
    bus_timeout=1e6, bus_bursting=False, bus_interconnect="shared", bus_arbiter="default",
    bus_low_latency=False,
    # The CPU.
    cpu_type="vexriscv", cpu_reset_address=None, cpu_variant=None, cpu_cfu=None, cfu_filename=None,
    # The memories in block RAM.
    integrated_rom_size=0, integrated_rom_mode="rx", integrated_rom_init=None,
    integrated_sram_size=8192, integrated_sram_init=None,
    integrated_main_ram_size=0, integrated_main_ram_init=None,
    # The CSR bus and the interrupts.
    csr_data_width=32, csr_address_width=14, csr_paging=2048, csr_ordering="big", irq_n_irqs=32,
    # The identifier, the UART, the bridges, the CPU debug.
    ident="", ident_version=False,
    with_uart=True, uart_name="serial", uart_baudrate=115200, uart_fifo_depth=16, uart_pads=None,
    uart_with_dynamic_baudrate=False, uart_rx_fifo_rx_we=False,
    with_uartbone=False, with_jtagbone=False, jtagbone_chain=1,
    with_cpu_jtag_debug=False, cpu_jtag_debug_chain=4, cpu_jtag_debug_clk_freq=10e6, cpu_jtag_debug_transport="user",
    # The timer, the controller, the watchdog.
    with_timer=True, timer_uptime=False, with_ctrl=True,
    with_watchdog=False, watchdog_width=32, watchdog_reset_delay=None,
    **kwargs)
```

The targets pass `--integrated-rom-size=0x20000` by default (the parser's default, resized to
the BIOS), the class itself defaults to 0. `--bus-*` also covers `--bus-address-width`,
`--bus-addressing`, `--bus-timeout`, `--bus-bursting`, `--bus-interconnect`
(`shared` or `crossbar`), `--bus-arbiter` and `--bus-low-latency`; `--csr-paging` and
`--csr-ordering` the CSR bus; `--uart-fifo-depth` the UART; `--jtagbone-chain`,
`--cpu-jtag-debug-chain`, `--cpu-jtag-debug-transport` the bridges and the debug TAP.

</details>

## The helpers

One `add_*` per core or feature, with the page that uses it; the signatures are below the table.

| Helper | What it adds |
| --- | --- |
| `add_rom`, `add_ram` | A block RAM on the bus, its region, `CONFIG_<NAME>_INIT` when it has contents. |
| `add_sdram` | The LiteDRAM controller, the `main_ram` region, the L2 cache, the CPU's direct ports, `sdram_phy.h`. |
| `add_hyperram`, `add_spi_flash`, `add_spi_ram` | HyperRAM, a memory-mapped LiteSPI flash (XIP, `FLASH_BOOT_ADDRESS`), SPI RAM. |
| `add_cpu` | The CPU: its buses as masters, IO regions, interrupts, reset address, DMA bus, `CPU_*` constants. |
| `add_controller`, `add_identifier`, `add_timer`, `add_watchdog` | Reset and scratch registers, the identifier, the timer the BIOS needs, a watchdog. |
| `add_uart`, `add_uartbone`, `add_jtagbone` | The console UART and the [host bridges](Host-Bridges.md). |
| `add_ethernet`, `add_etherbone` | LiteEth: the MAC for the CPU, the Etherbone bridge, or both on one PHY. |
| `add_pcie` | LitePCIe: the endpoint, the MMAP bridge, the DMAs, MSI ([Create a PCIe SoC](Create-A-PCIe-SoC.md)). |
| `add_sata`, `add_sdcard`, `add_spi_sdcard` | LiteSATA and LiteSDCard with their DMAs, or the bit-banged SPI SD card. |
| `add_i2c_master`, `add_spi_master` | I2C and SPI masters with their interrupts and constants. |
| `add_video_colorbars`, `add_video_terminal`, `add_video_framebuffer` | A test pattern, a text terminal on the UART stream, a framebuffer in main RAM. |
| `add_cpu_jtag_debug` | The CPU debug TAP on a USER chain or through CSRs ([Debug with GDB](Debug-With-GDB.md)). |
| `add_constant`, `add_config` | A `#define` in `soc.h` (`CONFIG_` prefix with `add_config`) for the BIOS and the firmware. |
| `add_soc_reset_request` | A signal that resets the SoC (a watchdog, a PCIe link down). |

<details>
<summary>The signatures</summary>

```python
add_rom(name, origin, size, contents=[], mode="rx")
add_ram(name, origin, size, contents=[], mode="rwx")
add_sdram(name, phy, module, origin=None, size=None, l2_cache_size=8192, with_bist=False, ...)
add_hyperram(name, pads, origin, size, ...)
add_spi_flash(name, mode="4x", clk_freq=20e6, module=None, ...)
add_spi_ram(name, mode="4x", clk_freq=20e6, module=None, ...)
add_cpu(name="vexriscv", variant="standard", reset_address=None, cfu=None)
add_controller(name="ctrl"); add_identifier(name="identifier", identifier="LiteX SoC", with_build_time=True)
add_timer(name="timer0"); add_watchdog(name="watchdog0", width=32, crg_rst=None, reset_delay=None)
add_uart(name="uart", uart_name="serial", baudrate=115200, fifo_depth=16)
add_uartbone(name="uartbone", uart_name="serial", baudrate=115200)
add_jtagbone(name="jtagbone", chain=1)
add_ethernet(name="ethmac", phy, nrxslots=2, ntxslots=2, with_timestamp=False, local_ip=None, remote_ip=None, ...)
add_etherbone(name="etherbone", phy, ip_address="192.168.1.50", mac_address=0x10e2d5000000, udp_port=1234, with_ethmac=False, ...)
add_pcie(name="pcie", phy, ndmas=0, with_dma_buffering=True, with_msi=True, ...)
add_sata(name="sata", phy, mode="read+write", with_bist=False)
add_sdcard(name="sdcard", ...); add_spi_sdcard(name="spisdcard", spi_clk_freq=400e3)
add_i2c_master(name="i2c", pads=None); add_spi_master(name="spi", pads=None, data_width=8, spi_clk_freq=1e6)
add_video_colorbars(name="video_colorbars", phy, timings="800x600@60Hz", clock_domain="sys")
add_video_terminal(name="video_terminal", phy, timings="800x600@60Hz", clock_domain="sys")
add_video_framebuffer(name="video_framebuffer", phy, timings="800x600@60Hz", clock_domain="sys", format="rgb888", base=0x40c00000)
add_cpu_jtag_debug(chain=4, clk_freq=10e6, clock_domain="sys", transport="user")
add_constant(name, value=None); add_config(name, value=None); add_soc_reset_request(name, reset)
```

</details>

The convention: `name` is the CSR and IRQ name and the prefix of the constants, and the
module is `self.<name>` afterwards (`self.sdram`, `self.ethmac`, `self.pcie_phy`), so a target
can refine it after the call.

## Builder options

Available on every target, one row per group:

| Option | Meaning |
| --- | --- |
| `--build`, `--load`, `--flash` | Build; load the bitstream; write it to the flash. |
| `--toolchain` | The toolchain among those of the platform (the first one by default). |
| `--output-dir`, `--gateware-dir`, `--software-dir` | Where things go: `build/<platform>/{gateware,software}` by default. |
| `--no-compile`, `--no-compile-gateware`, `--no-compile-software` | Generate without running the toolchain, or `make`, or neither. |
| `--soc-csv`, `--soc-json`, `--soc-svd`, `--memory-x` | Extra outputs (`--csr-*` are the old names of the first three). |
| `--doc`, `--hierarchical-verilog` | The Sphinx documentation; a hierarchical Verilog instead of a flat one. |
| `--build-backend {litex,edalize}`, `--build-log`, `--no-build-log` | The build backend; the log is `<output-dir>/litex.log`. |
| `--bios-lto`, `--bios-format`, `--bios-console`, `--bios-no-ansi` | BIOS build options ([BIOS](BIOS.md)). |
| `--bios-stack-margin`, `--libc-mode {minimal,full}`, `--no-integrated-rom-auto-size` | More of them: the stack check, the libc, the ROM size. |
| `--build-bundle [PATH]`, `--bundle-*` | Record the inputs of the build in an archive to replay it elsewhere ([Tools](Tools.md)). |
| `--log-filename`, `--log-level` | Logging. |

`--build --no-compile-gateware` gives the software support of a SoC without an FPGA toolchain
([Create a minimal SoC](Create-A-minimal-SoC.md#4-build-it-without-the-fpga-toolchain-first)).

## Finalization checks

- The CPU reset address must fall in a region (the ROM by default); `--integrated-rom-size=0`
  with a CPU needs `--cpu-reset-address` in the flash or the main RAM.
- The BIOS needs the `timer0` CSRs and the `rom` and `sram` regions; a design with
  `--no-timer` builds without BIOS (`--integrated-rom-init` for your own code).
- Regions must not overlap and uncached regions must sit in the CPU's IO regions; the handler
  raises an error with the conflicting names.
- A peripheral is seen by the software only if it has CSRs (a location) or a bus region: a
  module that is not an attribute of the SoC (or added with `add_module`) is invisible.

## Next

- [SoC builder](SoC-builder.md): what these arguments and helpers do, in prose.
- [Create a minimal SoC](Create-A-minimal-SoC.md): the options at work on a forty-line target.
- [BIOS](BIOS.md): the `--bios-*` options and the boot sequence.
- [Build backends](Build-Backends.md): the `--toolchain` values and the toolchain options.
