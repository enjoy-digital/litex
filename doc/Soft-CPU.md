All LiteX SoCs need some type of CPU to operate correctly. Most use an "Soft CPU" embedded in the gateware for this purpose, but in some cases a host computer is used instead (for example this can be true in the PCIe card case).

# Summary of Soft CPUs

Currently the supported Soft CPUs are:

 * [`lm32`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/lm32) -- a [LatticeMico32](https://en.wikipedia.org/wiki/LatticeMico32) soft core.

*   [`or1k`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/mor1kx) -- an [OpenRISC 1000](https://openrisc.io/or1k.html) soft core (see also [Open RISC on Wikipedia](https://en.wikipedia.org/wiki/OpenRISC)).

*   [`picorv32`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/picorv32) -- a [Small RISC V core by Clifford Wolf](https://github.com/cliffordwolf/picorv32), implementing the `rv32imc` instruction set (or configured subsets)

*   [`vexriscv`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/vexriscv) -- an [FPGA Friendly RISC V core by SpinalHDL](https://github.com/SpinalHDL/VexRiscv), implementing the `rv32im` instruction set (hardware multiply optional)

*   [`minerva`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/minerva) -- an Minerva is a CPU core that currently implements the RISC-V RV32I instruction set and its microarchitecture is described in plain Python code using the [nMigen toolbox](https://github.com/m-labs/nmigen).

# Soft CPU Variants

Most of these CPUs have multiple configuration "variants" which customize the configuration to target a specific type of firmware and performance. All these CPUs can be used with your own bare metal firmware.

## `minimal`

Aliases: `min`

Minimal is the smallest possible working configuration for a given CPU type. These features frequently disables a large number of useful such as illegal instruction exceptions and similar. It should only be used if the absolute smallest configuration is needed.

### Supported CPUs

 * lm32
 * picorv32
 * vexriscv

## `lite`

**Aliases**: `zephyr`, `nuttx`, `light`

Lite is the configuration which should work okay for bare metal firmware and RTOS like NuttX or Zephyr on small big FPGAs like the Lattice iCE40 parts. It can also be used for designs which are more resource constrained.

### Recommended FPGAs

 * Lattice iCE40 Series - iCE40HX, iCE40LP, iCE40UP5K
 * Any resource constrained design.

### Supported CPUs

 * lm32
 * vexriscv

## `standard`

**Aliases**: `std`

Standard is the default configuration which should work well for bare metal firmware and RTOS like NuttX or Zephyr on modern big FPGAs.

### Supported CPUs

 * lm32
 * minerva
 * picorv32
 * or1k
 * vexriscv

### Recommended FPGAs

 * Xilinx Series 7 - Artix 7, Kintex 7, Spartan 7
 * Xilinx Spartan 6
 * Lattice ECP5

## `linux`

This target enables CPU features such as MMU that are required to get Linux booting.

### Supported CPUs

 * or1k
 * vexriscv

---

# Soft CPU Extensions

Extensions are added to the CPU variant with a `+`. For example a `minimal` variant with the `debug` extension would be `minimal+debug`.

## `debug`

The debug extension enables extra features useful for debugging. This normally includes things like JTAG port.

### Supported CPUs

 * vexriscv

## TODO - `mmu`

The `mmu` extension enables a memory protection unit.

### Supported CPUs

 * lm32 (untested)
 * vexriscv
 * or1k

## TODO - `hmul`

The `hmul` extension enables hardware multiplication acceleration.

---

# Binutils + Compiler

 * lm32 support was added to upstream GCC around ~2009, no clang support.
 * or1k support was added to upstream GCC in version 9.0.0, clang support was added upstream in version XXX
 * riscv support (VexRISCV, PicoRV32 and Minerva) was added to upstream GCC in version 7.1.0, clang support was added upstream in version 3.1

You can compile your own compiler, download a precompiled toolchain or use an environment like [TimVideos LiteX BuildEnv](https://github.com/timvideos/litex-buildenv/) which provides precompiled toolchain for all three architectures.

Note: RISC-V toolchains support or require various extensions. Generally `rv32i` is used on smaller FPGAs, and `rv32im` on larger FPGAs -- the `rv32im` adds hardware multiplication and division (see [RISC V ISA base and extensions on Wikipedia](https://en.wikipedia.org/wiki/RISC-V#ISA_base_and_extensions) for more detail).

---

# SoftCPU options

## lm32 - [LatticeMico32](https://github.com/m-labs/lm32)

[LatticeMico32](https://en.wikipedia.org/wiki/LatticeMico32) soft core, small and designed for an FPGA.

### CPU Variants

 * minimal
 * lite
 * standard

### Tooling support

 * Upstream GCC
 * Upstream Binutils

### OS Support

 * No upstream Linux, very old Linux port
 * Upstream NuttX
 * No Zephyr support

### Community

 * No current new activity

---

## [mor1k - OpenRISC](https://github.com/openrisc/mor1kx)

An [OpenRISC 1000](https://openrisc.io/or1k.html) soft core (see also [Open RISC on Wikipedia](https://en.wikipedia.org/wiki/OpenRISC)).

### CPU Variants

 * standard
 * linux

### Tooling support

 * Upstream GCC
 * Upstream Binutils
 * Upstream clang

### OS support

 * No Zephyr support
 * No NuttX support
 * Upstream Linux

### Community

 * Reasonable amount of activity.

---

## RISC-V - [VexRiscv](https://github.com/SpinalHDL/VexRiscv)

A [FPGA Friendly RISC V core by SpinalHDL](https://github.com/SpinalHDL/VexRiscv), implementing the `rv32im` instruction set (hardware multiply optional).

### CPU Variants

 * minimal
 * minimal_debug
 * lite
 * lite_debug
 * standard
 * standard_debug
 * linux

### Tooling support

 * Upstream GCC
 * Upstream Binutils
 * Upstream clang

### OS support

 * Upstream Zephyr
 * Unknown NuttX support
 * Upstream Linux (in progress)

### Community

 * Lots of current activity
 * Currently supported under both LiteX & MiSoC

## RISC-V - [picorv32](https://github.com/cliffordwolf/picorv32/)

A [small RISC V core by Clifford Wolf](https://github.com/cliffordwolf/picorv32), implementing the `rv32imc` instruction set (or configured subsets).

### CPU Variants

 * minimal
 * standard

### Tooling support

 * Upstream GCC
 * Upstream Binutils
 * Upstream clang

### OS support

 * Out of tree Zephyr
 * Unknown NuttX support
 * Too small for Linux

### Community

 * Some activity

## RISC-V - [`minerva`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/minerva)

The Minerva is a CPU core that currently implements the RISC-V RV32I instruction set and its microarchitecture is described in plain Python code using the [nMigen toolbox](https://github.com/m-labs/nmigen).

### CPU Variants

 * standard

### Tooling support

 * Upstream GCC
 * Upstream Binutils
 * Upstream clang

### OS support

 * Unknown Zephyr support
 * Unknown NuttX support
 * Unknown Linux support

### Community

 * Some activity
