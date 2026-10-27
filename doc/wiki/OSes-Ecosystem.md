# LiteX OSes Ecosystem

What runs on the CPU of a LiteX SoC, from the BIOS to Linux. LiteX generates the software
support from the SoC itself: C headers (`csr.h`, `soc.h`, `mem.h`), linker regions
(`memory.x`), the `csr.csv/json/svd` descriptions and the device trees for Linux, Zephyr and
Renode (`litex_json2dts_linux`, `litex_json2dts_zephyr`, `litex_json2renode`), so that the
software always matches the hardware configuration. Pick what fits the job:

| | Runs on | Good for |
| --- | --- | --- |
| [BIOS and bare metal](#bios-and-bare-metal) | every CPU | bring-up, control firmware, the smallest SoCs |
| [RTOS](#rtos): Zephyr, FreeRTOS, NuttX | VexRiscv, VexiiRiscv (Zephyr) and other RV32 cores | real-time firmware with a scheduler and a driver model |
| [MicroPython, Rust, MQuickJS](#micropython-rust-and-others) | RV32 cores | scripting the SoC, memory-safe firmware |
| [Linux](#linux) | VexRiscv-SMP, NaxRiscv, VexiiRiscv, Rocket, Mor1kx, BlackParrot, Microwatt, hard CPUs | the full software ecosystem, networking, storage |

## BIOS and bare metal

Every SoC with a CPU gets the [LiteX BIOS](https://github.com/enjoy-digital/litex/tree/master/litex/soc/software/bios):
it initializes the SoC (DRAM training, Ethernet, SD card...), provides a console with commands
to inspect memory and registers, and loads the application through the
[boot methods](Load-Application-Code-To-CPU.md) (serial, Ethernet/TFTP, SPI flash, SD card,
SATA). It is built by the Builder with picolibc; `--libc-mode minimal` (the default) or
`full`, `--bios-console`, `--bios-format` and `--bios-lto` tune its size and features.

Bare-metal applications are written in C/C++ against the generated headers and the small
libraries of `litex/soc/software/` (`libbase`, `liblitedram`, `libliteeth`, `liblitesdcard`,
`liblitesata`, `liblitespi`...): the [demo application](https://github.com/enjoy-digital/litex/tree/master/litex/soc/software/demo)
(`litex_bare_metal_demo --build-path=build/<board>`, then `litex_term /dev/ttyUSBx --kernel=demo.bin`)
is the template: console, LEDs, a donut. See
[Create and load software](Create-And-Load-Software-To-The-CPU.md).

## RTOS

- [Zephyr](https://www.zephyrproject.org/): the `litex_vexriscv` and `litex_vexiiriscv`
  boards and the `litex` SoC family are upstream in Zephyr; the device tree and the Kconfig
  overlay come from `litex_json2dts_zephyr`. See [Run Zephyr on your SoC](Run-Zephyr-On-Your-SoC.md)
  and [zephyr-on-litex-vexriscv](https://github.com/litex-hub/zephyr-on-litex-vexriscv).
- [FreeRTOS](https://github.com/enjoy-digital/freertos-on-litex): FreeRTOS V11 as LiteX
  firmware on VexRiscv, with blinky, queues and full demos, validated in `litex_sim` (no board
  needed) and on hardware.
- [NuttX](https://nuttx.apache.org/): the `litex` RISC-V architecture and the Arty A7 board
  are upstream (`arch/risc-v/src/litex`, `boards/risc-v/litex/arty_a7`), with LiteEth
  networking.

## MicroPython, Rust and others

- [MicroPython](https://github.com/litex-hub/micropython) (`ports/litex`, maintained in
  LiteX-Hub): Python on the SoC, see [Run MicroPython](Run-MicroPython-CircuitPython-On-Your-SoC.md).
  The [FuPy](https://github.com/fupy/micropython) port (LM32, OpenRISC) and the CircuitPython
  port are historical.
- Rust: the Builder's `--csr-svd` output feeds `svd2rust` for a peripheral access crate;
  [rust-litex-hal](https://github.com/pepijndevos/rust-litex-hal) implements `embedded-hal`
  for the LiteX cores, [rust-litex](https://github.com/tomtor/rust-litex) runs Rust on the
  Linux SoC.
- [MQuickJS](https://github.com/enjoy-digital/mquickjs-on-litex): Bellard's JavaScript engine
  bare metal on VexRiscv, with access to the CSRs from JavaScript, in `litex_sim` and on boards.

## Linux

- [Linux-on-LiteX-VexRiscv](https://github.com/litex-hub/linux-on-litex-vexriscv): the
  reference, a VexRiscv-SMP (1 to 8 cores) SoC with LiteDRAM, LiteEth, LiteSDCard, LiteSATA,
  PCIe, USB OHCI, framebuffer... on Xilinx, Intel, Lattice, Microsemi and Efinix boards;
  OpenSBI + Linux + Buildroot rootfs loaded by the BIOS. NaxRiscv and VexiiRiscv (64-bit,
  MMU) boot Linux too, with the `linux` variants of the [LiteX-Boards](https://github.com/litex-hub/litex-boards)
  targets (see [CPUs](CPUs.md) and the [JTAG/GDB page](JTAG-GDB-Debugging-with-VexRiscv-SMP-NaxRiscv-VexiiRiscv-CPUs.md)).
- [Linux-on-LiteX-Rocket](https://github.com/litex-hub/linux-on-litex-rocket): 64-bit
  RocketChip, upstream Linux (BBL + initramfs), maintained by Gabriel Somlo.
- Mor1kx (OpenRISC), BlackParrot and Microwatt (POWER) also boot Linux on LiteX SoCs:
  [Run Linux on your SoC](Run-Linux-On-Your-SoC.md).
- Hard CPUs: on Zynq-7000, ZynqMP, Cyclone V and Agilex HPS the vendor Linux runs on the
  hard cores and talks to the LiteX gateware through the AXI bridges
  (`litex_server --devmem` gives the host tools access from Linux).
- Upstream support: the Linux kernel has the LiteUART, LiteEth, LiteSDCard (`litex_mmc`)
  and SoC controller drivers; [barebox](https://www.barebox.org/) has a `litex-linux` board
  with serial, SPI flash and Ethernet drivers; U-Boot has the LiteEth driver.
- Larger systems built on these: [OpenWrt](https://github.com/enjoy-digital/litex_openwrt_test),
  [Debian](https://github.com/roryt12/RISCV64-Debian-Linux-on-FPGA-with-Litex) (archived),
  [Xous](https://github.com/betrusted-io/xous-core) (the Precursor microkernel, on a LiteX SoC).

Simulation of the software without a board: `litex_sim` runs the SoC with its BIOS and
firmware in Verilator ([SoC-Simulator](SoC-Simulator.md)), [Renode](Generate-Renode-simulation.md)
runs Linux/Zephyr images on a model of the SoC, and the QEMU co-simulation runs the CPU in
QEMU against the simulated gateware.
