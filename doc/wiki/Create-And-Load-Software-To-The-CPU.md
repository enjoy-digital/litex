# Create and load software to the CPU

Every LiteX SoC with a CPU gets the [BIOS](BIOS.md); your application is built the same way
against the headers the Builder generates, loaded into the main RAM by one of the boot methods
(or placed in the ROM/flash), and talks to your cores through the `csr.h` accessors. The
template is the demo application of LiteX (`litex/soc/software/demo/`: a console with
`help`, `reboot`, `led`, a donut).

## 1. Build the SoC, then the application

```sh
python3 -m litex_boards.targets.digilent_arty --build --load          # the SoC (gateware + BIOS)
litex_bare_metal_demo --build-path=build/digilent_arty                 # the demo: demo.bin, demo.fbi
litex_term /dev/ttyUSB1 --kernel=demo.bin                              # boot it over the serial port
```

`litex_bare_metal_demo` copies the template to `./demo/`, adapts the linker script and runs
`make` with the SoC's `build/<board>/` as `BUILD_DIR`: the generated headers, the libraries
(`libbase`, `libc`, `liblitedram`...) and the compiler flags of the CPU come from there, so the
application always matches the SoC. `--with-cxx` enables C++ (`hellocpp.cpp`), `--mem` picks
the region where the code runs (`main_ram` by default; `rom` or `spiflash` for execute in
place), `--runtime-mem` the region of `.data`/`.bss`/stack (`sram` by default; `main_ram` for
a big application). Without a board, the same works in [litex_sim](SoC-Simulator.md)
(`--build-path=build/sim`, then `litex_sim --ram-init=demo.bin`).

## 2. What the template contains

| File | Role |
| --- | --- |
| `Makefile` | Includes `variables.mak` (CPU flags, packages, libc mode) and `common.mak` from the build, compiles with the CPU's GCC, links the objects with `crt0.o` (the CPU's start-up code from `litex/soc/cores/cpu/<cpu>/crt0.S`) and the libraries, produces `demo.elf`, `demo.bin`. |
| `linker.ld` | Includes `generated/output_format.ld` and `generated/regions.ld` (the memory regions of the SoC: `rom`, `sram`, `main_ram`...), places `.text`/`.rodata` in `main_ram`, `.data`/`.bss`/stack in `sram`. |
| `main.c` | `uart_init()`, the console loop (`readstr`, `get_token`), the commands, `irq_setmask`/`irq_setie` for the interrupts. |
| `helloc.c`, `hellocpp.cpp`, `donut.c` | The example commands. |
| `demo.fbi` | The flash boot image (`crcfbigen`: an 8-byte header with length and CRC for the BIOS `flashboot`). |

Copy the directory to start your own firmware: rename the objects in the Makefile, keep
`BUILD_DIR` pointing at the SoC build, add your sources. The generated headers you include:

```c
#include <generated/csr.h>     // <core>_<register>_read()/_write(), CSR_<CORE>_<REG>_ADDR, fields
#include <generated/soc.h>     // CONFIG_CLOCK_FREQUENCY, CONFIG_CPU_*, <CORE>_INTERRUPT, the constants
#include <generated/mem.h>     // <REGION>_BASE / <REGION>_SIZE
#include <irq.h>               // irq_setmask(), irq_setie(), irq_getmask(), irq_pending()
#include <libbase/uart.h>      // uart_init(), uart_isr(), readchar(), readchar_nonblock()
#include <libbase/console.h>   // readstr helpers, printf goes to the UART through picolibc
#include <libbase/i2c.h>, <liblitedram/sdram.h>, <libliteeth/udp.h>, <liblitesdcard/sdcard.h>, ...
```

`printf` and the libc come from picolibc (`--libc-mode full` for the complete `printf`,
`--bios-format float` when you print floats); `timer0` gives `busy_wait()`/`busy_wait_us()`
and the uptime (`--timer-uptime`).

## 3. Interrupts

```c
#include <irq.h>
#include <generated/csr.h>

void isr(void)
{
    unsigned int irqs = irq_pending() & irq_getmask();
#ifdef CSR_UART_BASE
    if (irqs & (1 << UART_INTERRUPT))
        uart_isr();
#endif
    if (irqs & (1 << PWM_INTERRUPT)) {
        pwm_ev_pending_write(pwm_ev_pending_read());   // acknowledge
        ...
    }
}
```

The CPU's `crt0.S` calls `isr()`; the line numbers are the `<CORE>_INTERRUPT` constants of
`soc.h`, the cores' `ev_enable`/`ev_pending` registers select and acknowledge the events
(`irq.h` of each CPU implements the mask and enable with its CSRs). CPUs without interrupt
support (`UART_POLLING` in `soc.h`) are polled.

## 4. Load it

| Method | Command | When |
| --- | --- | --- |
| Serial (SFL) | `litex_term /dev/ttyUSB1 --kernel=demo.bin [--kernel-adr=0x40000000]` | Development: a few seconds for a small binary, the BIOS waits for it at boot. |
| Network (TFTP) | copy `demo.bin` as `boot.bin` in the TFTP root (`--with-ethernet`, `REMOTEIP` is the server) | Big binaries, Linux images. |
| SD card / SATA | `boot.bin` or `boot.json` on a FAT partition | Autonomous boards. |
| SPI flash | `python3 target.py --flash` with the firmware at `FLASH_BOOT_ADDRESS` (`demo.fbi`, with the header), or the BIOS `flash_write`/`flash_from_sdcard` | Production: the BIOS copies it to RAM at boot (or runs it in place with `--mem spiflash`). |
| ROM | `--integrated-rom-init=demo.bin` (the application replaces the BIOS; link it with `--mem rom`) | Small SoCs without main RAM, simulation (`--rom-init`). |
| Main RAM at reset | `--integrated-main-ram-init=demo.bin` (block RAM) with `--cpu-reset-address` | Simulation and self-contained test SoCs. |

`litex_term --images images.json` loads several files at once (the same format as
`boot.json`), `--serial-boot` starts the upload without waiting for the prompt. The
mechanisms are described in [Load application code to the CPU](Load-Application-Code-To-CPU.md)
and [BIOS](BIOS.md).

## 5. Beyond C

- **Rust**: `--memory-x memory.x` and `--soc-svd soc.svd` give the linker regions and the
  peripheral description (`svd2rust`); [rust-litex-hal](https://github.com/pepijndevos/rust-litex-hal)
  implements `embedded-hal` on the LiteX cores.
- **RTOS and OSes**: [Zephyr](Run-Zephyr-On-Your-SoC.md), [FreeRTOS](https://github.com/enjoy-digital/freertos-on-litex),
  NuttX, [MicroPython](Run-MicroPython-CircuitPython-On-Your-SoC.md) and
  [Linux](Run-Linux-On-Your-SoC.md) take the SoC description through the generated device trees
  ([OSes ecosystem](OSes-Ecosystem.md)).
- **Debugging**: `printf` over the UART, the BIOS `mem_*` commands, [GDB over JTAG](JTAG-GDB-Debugging-with-VexRiscv-CPU.md),
  the registers from the host with [litex_cli](Host-Bridges.md) while the firmware runs.
