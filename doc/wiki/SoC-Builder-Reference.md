The tables behind the [SoC builder](SoC-builder.md): the arguments of `SoCCore` and their
command-line options, the `add_*` helpers, the options of the Builder and the checks run at
finalization. The values are those of `litex/soc/integration/soc.py` and `builder.py` on
2026-10-27; `python3 target.py --help` prints the live list for a target.

## SoCCore arguments

`SoCCore(platform, sys_clk_freq, ...)` arguments and their defaults, which are also the
`--`-options of the targets:

| Argument | Default | Option | Meaning |
| --- | --- | --- | --- |
| `bus_standard`, `bus_data_width`, `bus_address_width`, `bus_addressing`, `bus_timeout`, `bus_bursting`, `bus_interconnect`, `bus_arbiter`, `bus_low_latency` | `wishbone`, 32, 32, word (byte for AXI), 1e6 cycles, off, `shared`, `default`, off | `--bus-*` | The main bus ([below](SoC-builder.md#the-bus-and-its-handler)). |
| `cpu_type`, `cpu_variant`, `cpu_reset_address`, `cpu_cfu` | `vexriscv`, the CPU's default (`standard`), the `rom` origin, none | `--cpu-type`, `--cpu-variant`, `--cpu-reset-address`, `--cpu-cfu` | The CPU ([CPUs](CPUs.md)). `--cpu-type=None` for a SoC without CPU. |
| `integrated_rom_size`, `integrated_rom_init`, `integrated_rom_mode` | 0x20000 (auto-sized to the BIOS), none, `rx` | `--integrated-rom-size`, `--integrated-rom-init` | The ROM in block RAM holding the BIOS (or your firmware with `--integrated-rom-init`). |
| `integrated_sram_size`, `integrated_main_ram_size` | 0x2000, 0 | `--integrated-sram-size`, `--integrated-main-ram-size` | SRAM (stack, BIOS data) and main RAM in block RAM; a DRAM comes from `add_sdram` instead. |
| `csr_data_width`, `csr_address_width`, `csr_paging`, `csr_ordering` | 32, 14, 0x800, `big` | `--csr-*` | The CSR bus ([CSR-Bus](CSR-Bus.md)). |
| `ident`, `ident_version` | "", `False` | `--ident`, `--no-ident-version` | The identifier string (`litex_cli --ident`, the BIOS banner), with the build time. |
| `with_uart`, `uart_name`, `uart_baudrate`, `uart_fifo_depth` | `True`, `serial`, 115200, 16 | `--no-uart`, `--uart-name`, `--uart-baudrate`, `--uart-fifo-depth` | The console: `serial`, `crossover` (through a bridge), `crossover+uartbone`, `jtag_uart`, `usb_acm`, `sim`, `stub`, `stream`. |
| `with_uartbone`, `with_jtagbone`, `jtagbone_chain` | off, off, 1 | `--with-uartbone`, `--with-jtagbone`, `--jtagbone-chain` | [Host bridges](Host-Bridges.md). |
| `with_cpu_jtag_debug`, `cpu_jtag_debug_transport`, `cpu_jtag_debug_chain` | off, `user`, 4 | `--with-cpu-jtag-debug`, `--cpu-jtag-debug-transport`, `--cpu-jtag-debug-chain` | CPU debug over JTAG ([JTAG/GDB](Debug-With-GDB.md)). |
| `with_timer`, `timer_uptime`, `with_ctrl`, `with_watchdog` | on, off, on, off | `--no-timer`, `--timer-uptime`, `--no-ctrl`, `--with-watchdog` | Timer (required by the BIOS), SoC controller (reset, scratch, bus errors), watchdog. |
| `irq_n_irqs` | 32 | | Number of interrupt lines. |

## The helpers

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

## Builder options

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

## Finalization checks

- The CPU reset address must fall in a region (the ROM by default); an `--integrated-rom-size 0`
  with a CPU needs `--cpu-reset-address` in the flash or main RAM.
- The BIOS needs the `timer0` CSRs and the `rom` and `sram` regions (`check_bios_requirements`);
  a design with `--no-timer` builds without BIOS (`--integrated-rom-init` for your own code).
- Regions must not overlap and uncached regions must sit in the CPU's IO regions; the handler
  raises a clear error with the conflicting names.
- A peripheral is seen by software only if it has CSRs (a location) or a bus region: a module
  that is not an attribute of the SoC (or added with `add_module`) is invisible.
