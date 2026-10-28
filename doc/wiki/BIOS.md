The LiteX BIOS is the small program the Builder compiles for every SoC with a CPU
(`litex/soc/software/bios/`, C, built on picolibc): it initializes the SoC (DRAM calibration,
Ethernet, storage), gives a console on the UART to inspect the hardware, and loads the
application through one of the boot methods. It is the first thing that runs on a new board and
the reference user of the generated headers; your own firmware ([Create and load software](Write-Firmware-For-Your-SoC.md))
is built the same way against the same `csr.h`/`soc.h`/`mem.h`.

![The BIOS boot flow](images/litex-bios-boot.svg)

```
        __   _ __      _  __
       / /  (_) /____ | |/_/
      / /__/ / __/ -_)>  <
     /____/_/\__/\__/_/|_|
   Build your hardware, easily!

 (c) Copyright 2012-2026 Enjoy-Digital
 (c) Copyright 2007-2015 M-Labs

 BIOS built on Oct 27 2026 10:02:11
 BIOS CRC passed (b1a3c4d5)

 LiteX git sha1: 7457e1379

--=============== SoC ==================--
CPU:            VexRiscv @ 100MHz
BUS:            wishbone 32-bit @ 4GiB
CSR:            32-bit data
ROM:            128.0KiB
SRAM:           8.0KiB
L2:             8.0KiB
SDRAM:          256.0MiB 16-bit @ 800MT/s (CL-6 CWL-5)

--========== Initialization ============--
Initializing SDRAM @0x40000000...
...
Memtest at 0x40000000 (2.0MiB)...
  Write: 0x40000000-0x40200000 2.0MiB
   Read: 0x40000000-0x40200000 2.0MiB
Memtest OK
Memspeed at 0x40000000 (Sequential, 2.0MiB)...
  Write speed: 23.5MiB/s
   Read speed: 15.2MiB/s

--============== Boot ==================--
Booting from serial...
Press Q or ESC to abort boot completely.
sL5DdSMmkekro
Timeout
No boot medium found

--============= Console ================--

litex>
```

## What it does at start-up

1. Enables the interrupts and the UART (the console), the I2C controllers.
2. Prints the banner: build date, BIOS CRC, LiteX git sha1, the SoC summary (CPU, bus, CSR,
   memories, DRAM configuration).
3. Initializes the memories and peripherals the SoC has: HyperRAM, SFP, Ethernet (with DHCP
   when enabled), SPI RAM, then the DRAM (LiteDRAM calibration, memtest and memspeed; a plain
   memtest when the main RAM is a block RAM), the SPI flash, the video framebuffer.
4. Runs the boot sequence (below). If nothing boots, or after `Q`/ESC, it drops to the console.

## The console

Commands have help (`help`, `help <command>`), history and completion. The common ones:

| Group | Commands |
| --- | --- |
| System | `help`, `ident`, `uptime`, `crc <addr> <len>`, `leds <value>`, `buttons`, `reboot`, `flush_cpu_dcache`, `flush_l2_cache` |
| Memory | `mem_list`, `mem_read <addr> [len]`, `mem_write <addr> <value> [count] [size]`, `mem_copy <dst> <src> [count]`, `mem_test <addr> [size]`, `mem_speed <addr> <size>` |
| Boot | `boot <addr> [r1] [r2] [r3]`, `serialboot`, `netboot [manifest]`, `flashboot`, `romboot`, `sdcardboot [manifest]`, `sataboot [manifest]` |
| DRAM (LiteDRAM) | `sdram_init`, `sdram_cal`, `sdram_test`, `sdram_bist`, `sdram_hw_test`, `sdram_spd`, `sdram_debug`, the `sdram_force_*`/`sdram_rst_*` delay and bitslip controls, `sdram_mr_write` |
| Ethernet (LiteEth) | `eth_local_ip`, `eth_remote_ip`, `eth_mac_addr`, `eth_dhcp`, `ping`, `mdio_read`/`mdio_write`/`mdio_dump`, `sfp`, `sfp_mdio_*` |
| Storage | `sdcard_detect`, `sdcard_init`, `sdcard_freq`, `sdcard_read`, `sdcard_write`; `sata_init`, `sata_read`, `sata_write`, `sata_sec2mem`, `sata_mem2sec`, `sata_rwtest` |
| Flash (LiteSPI) | `flash_write <offset> <addr> [count]`, `flash_erase_range <offset> <count>`, `flash_from_sdcard <file>` |
| I2C | `i2c_dev`, `i2c_scan`, `i2c_read`, `i2c_write`, `i2c_reset` |

Only the commands of the cores present in the SoC are compiled in.

## Boot methods

The BIOS tries the methods available in the SoC in this order (each has a priority that a
constant can change, and can be disabled):

| Priority | Method | Present when | What it does |
| --- | --- | --- | --- |
| 0 | **serial** | a UART | Prints the magic string and waits for `litex_term --kernel` to upload an image (the SFL protocol: `litex_term /dev/ttyUSB0 --kernel=demo.bin [--kernel-adr=0x40000000]`), times out otherwise. |
| 10 | **flash** | `FLASH_BOOT_ADDRESS` is defined | Reads an image at that offset of the SPI flash (8-byte header: length and CRC, then the payload), copies it to main RAM when there is one or executes it in place, and jumps to it. |
| 20 | **rom** | `ROM_BOOT_ADDRESS` is defined | Jumps to code already in a memory (an application linked in the ROM with the BIOS). |
| 30 | **sdcard** | LiteSDCard or SPI SD card | Mounts the FAT partition, loads `boot.json` or `boot.bin` (below). |
| 40 | **sata** | LiteSATA | Same with the SATA disk. |
| 50 | **net** | LiteEth MAC | TFTP from `REMOTEIP` (DHCP first when enabled): loads `boot.json` or `boot.bin`. |

`boot.bin` is loaded at the main RAM origin and executed. `boot.json` describes several images
and where to put them (Linux: OpenSBI, the kernel, the device tree, the rootfs):

```json
{
    "Image":     "0x40000000",
    "rv32.dtb":  "0x40ef0000",
    "rootfs.cpio": "0x41000000",
    "opensbi.bin": "0x40f00000",
    "bootargs": {"addr": "0x40f00000", "r1": "0x40ef0000"}
}
```

Without `bootargs`, the BIOS jumps to the last image. The complete description of the manifest,
the flash image bounds and the SRAM boot buffers is in
[doc/bios_config.md](https://github.com/enjoy-digital/litex/blob/master/doc/bios_config.md);
the practical page is [Load application code to the CPU](Write-Firmware-For-Your-SoC.md).

## Configuring the BIOS

The BIOS reads the generated `soc.h`: a core present in the SoC enables its commands and its
boot method, and a target tunes the BIOS with `soc.add_constant()`/`soc.add_config()`:

| Constant (`add_constant`) or config (`add_config`) | Effect |
| --- | --- |
| `ROM_BOOT_ADDRESS`, `FLASH_BOOT_ADDRESS` (+ `FLASH_BOOT_MAX_SIZE`, `FLASH_BOOT_REGION_BASE/SIZE`) | Enable the ROM and flash boots (`add_spi_flash` targets set the flash one). |
| `<SERIAL,FLASH,ROM,SDCARD,SATA,NET>_BOOT_PRIORITY`, `<...>_BOOT_DISABLE` | Reorder or disable a boot method. |
| `LOCALIP1..4`, `REMOTEIP1..4`, `MACADDR1..6`, `TFTP_SERVER_PORT` (69), `ETH_DYNAMIC_IP`, `ETH_WITH_DHCP`, `ETH_NETBOOT_SKIP_JSON` | Network boot parameters (`add_ethernet(local_ip=..., remote_ip=..., with_dhcp=True)` sets them). |
| `CONFIG_BIOS_NO_PROMPT`, `CONFIG_BIOS_NO_DELAYS`, `CONFIG_BIOS_NO_BUILD_TIME`, `CONFIG_BIOS_NO_CRC`, `CONFIG_BIOS_NO_BOOT` | Trim the BIOS: no banner, no delays (simulation), reproducible builds, no boot sequence. |
| `CONFIG_MAIN_RAM_INIT` (set by `--integrated-main-ram-init`) | Skip the memtest of a preloaded main RAM. |
| `UART_POLLING` | Set automatically when the CPU has no interrupts. |

The Builder options shape the binary: `--bios-console {full,no-history,no-autocomplete,lite,disable}`
and `--bios-no-ansi` for the console, `--bios-format {integer,float,double}` for `printf`,
`--bios-lto` and `--libc-mode {minimal,full}` for the size, `--bios-stack-margin` to fail the
build when the stack room is too small, and the `BIOS_ROM_BUDGET`/`BIOS_SRAM_BUDGET`
environment variables to enforce a footprint. The ROM is resized to the BIOS automatically
(`--no-integrated-rom-auto-size` keeps the requested size); `Memtest`, `Memspeed` and the
console take most of the space: a `lite` console and `minimal` libc fit small FPGAs.

## Where the code is

- `litex/soc/software/bios/main.c`: the start-up and the console; `boot.c`: the boot methods;
  `cmds/cmd_*.c`: the commands, one file per core.
- `litex/soc/software/libbase/`, `liblitedram/`, `libliteeth/`, `liblitesdcard/`,
  `liblitesata/`, `liblitespi/`: the libraries the BIOS and your firmware share (console,
  memtest, DRAM calibration, UDP/TFTP, FAT access, flash).
- `litex/soc/software/include/generated/`: the headers generated per SoC.
- `litex/soc/software/demo/`: the bare-metal application template
  (`litex_bare_metal_demo --build-path=build/<board>`).
