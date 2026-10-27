LiteX can create SoCs with or without CPU. Some simple SoCs don’t use any CPU (bridging SoCs for example), some SoCs use a CPU but external to the FPGA (PCIe SoCs for example where the CPU is directly the CPU of the Host machine) but in most of the cases the SoC embedded a "Soft CPU" to control the system and/or ease splitting tasks between software/hardware.

# [Hard CPUs page](Hard-core-CPUs.md)

# Summary of Soft CPUs

The authoritative CPU list is the LiteX CPU registry, built from the wrappers in:

```
litex/soc/cores/cpu/*/core.py
```

The currently registered CPU types can also be inspected from a LiteX checkout with:

```
python3 -c "from litex.soc.cores.cpu import CPUS; print('\n'.join(sorted(str(k) for k in CPUS if k is not None)))"
```

`--cpu-type=None` is also supported for SoCs without an embedded CPU.

Currently the supported Soft CPUs are:

* [`blackparrot`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/blackparrot) -- [BlackParrot](https://github.com/black-parrot/black-parrot), a 64-bit Linux-capable accelerator host multicore that implements the `rv64imafdc` instruction set.
* [`coreblocks`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/coreblocks) -- a RISC-V soft core.
* [`cortex_m1`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/cortex_m1) -- an ARM Cortex-M1 soft core.
* [`cortex_m3`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/cortex_m3) -- an ARM Cortex-M3 soft core.
* [`cv32e40p`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/cv32e40p) -- a CORE-V 32-bit RISC-V soft core.
* [`cv32e41p`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/cv32e41p) -- a CORE-V 32-bit RISC-V soft core.
* [`cva5`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/cva5) -- a 32-bit RISC-V soft core.
* [`cva6`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/cva6) -- a configurable RISC-V soft core.
* [`fazyrv`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/fazyrv) -- a 32-bit RISC-V soft core.
* [`femtorv`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/femtorv) -- a small 32-bit RISC-V soft core.
* [`firev`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/firev) -- a 32-bit RISC-V soft core.
* [`ibex`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/ibex) -- a 32-bit RISC-V soft core.
* [`kianv`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/kianv) -- a 32-bit RISC-V soft core.
* [`lm32`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/lm32) -- a [LatticeMico32](https://en.wikipedia.org/wiki/LatticeMico32) soft core.
* [`marocchino`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/marocchino) -- an OpenRISC soft core.
* [`microwatt`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/microwatt) -- a PowerPC soft core.
* [`minerva`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/minerva) -- a CPU core that currently implements the RISC-V RV32I instruction set with its microarchitecture described in plain Python code using the [nMigen toolbox](https://github.com/m-labs/nmigen).
* [`mor1kx`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/mor1kx) -- an [OpenRISC 1000](https://openrisc.io/or1k.html) soft core (see also [Open RISC on Wikipedia](https://en.wikipedia.org/wiki/OpenRISC)).
* [`naxriscv`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/naxriscv) -- a RISC-V soft core.
* [`neorv32`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/neorv32) -- [NEORV32](https://github.com/stnolting/neorv32), a small, platform-agnostic and highly extendable 32-bit RTOS-capable RISC-V core.
* [`openc906`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/openc906) -- a RISC-V soft core.
* [`picorv32`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/picorv32) -- a [Small RISC V core by Clifford Wolf](https://github.com/cliffordwolf/picorv32), implementing the `rv32imc` instruction set (or configured subsets).
* [`rocket`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/rocket) -- [Rocket Chip](https://github.com/chipsalliance/rocket-chip), a configurable, fully featured, 64-bit `rv64imafdc` capable core.
* [`sentinel`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/sentinel) -- a 32-bit RISC-V soft core.
* [`serv`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/serv) -- a small 32-bit RISC-V soft core.
* [`urv`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/urv) -- a 32-bit RISC-V soft core.
* [`vexiiriscv`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/vexiiriscv) -- an FPGA-friendly RISC-V soft core by SpinalHDL.
* [`vexriscv`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/vexriscv) -- an [FPGA Friendly RISC V core by SpinalHDL](https://github.com/SpinalHDL/VexRiscv), implementing the `rv32im` instruction set (hardware multiply optional).
* [`vexriscv_smp`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/vexriscv_smp) -- a Linux-capable SMP VexRiscv configuration.

# Soft CPU Variants

Most of these CPUs have multiple configuration variants which customize the configuration to target a specific type of firmware, performance and resource usage. All these CPUs can be used with your own bare metal firmware.

Variant names are CPU-specific, so the same variant name does not always imply the exact same micro-architecture or feature set on every CPU. The lists below summarize common variants; the CPU wrappers remain the authoritative source for exact support.

## `minimal`

Aliases: `min`

Minimal is the smallest possible working configuration for a given CPU type. These features frequently disables a large number of useful such as illegal instruction exceptions and similar. It should only be used if the absolute smallest configuration is needed.

### Supported CPUs

 * cva5
 * lm32
 * neorv32
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
 * neorv32
 * vexriscv

## `standard`

**Aliases**: `std`

Standard is the default configuration which should work well for bare metal firmware and RTOS like NuttX or Zephyr on modern big FPGAs.

### Supported CPUs

 * blackparrot
 * coreblocks
 * cortex_m1
 * cortex_m3
 * cv32e40p
 * cv32e41p
 * cva5
 * cva6
 * fazyrv
 * femtorv
 * firev
 * ibex
 * kianv
 * lm32
 * marocchino
 * microwatt
 * minerva
 * mor1kx
 * naxriscv
 * neorv32
 * openc906
 * picorv32
 * rocket
 * sentinel
 * serv
 * urv
 * vexiiriscv
 * vexriscv
 * vexriscv_smp

### Recommended FPGAs

 * Xilinx 7-Series - Artix7, Kintex7, Spartan7
 * Xilinx Spartan6
 * Lattice ECP5

## `full`

This target enables **all** features of each CPU.

### Supported CPUs

 * coreblocks
 * cva6
 * neorv32
 * rocket
 * vexriscv

## `linux`

This target enables CPU features such as MMU that are required to get Linux booting.

### Supported CPUs

 * coreblocks (`small_linux`)
 * marocchino
 * mor1kx
 * rocket
 * vexiiriscv
 * vexriscv
 * vexriscv_smp

---

# Soft CPU Extensions

Extensions are added to the CPU variant with a `+`. For example a `minimal` variant with the `debug` extension would be `minimal+debug`.

## `debug`

The debug extension enables extra features useful for debugging. This normally includes things like JTAG port.

### Supported CPUs

 * neorv32
 * vexriscv

## TODO - `mmu`

The `mmu` extension enables a memory protection unit.

### Supported CPUs

 * mor1kx
 * vexriscv

## TODO - `hmul`

The `hmul` extension enables hardware multiplication acceleration.

## TODO - `fpu`

The `fpu` extension enables a floating point acceleration unit.

### Supported CPUs

 * cv32e40p
 * mor1kx

---

# Binutils + Compiler

 * lm32 support was added to upstream GCC around ~2009, no clang support.
 * or1k support was added to upstream GCC in version 9.0.0, clang support was added upstream in version XXX
 * riscv support (VexRiscv, PicoRV32, Minerva, Rocket and others) was added to upstream GCC in version 7.1.0, clang support was added upstream in version 3.1

You can compile your own compiler, download a precompiled toolchain, install a RISC-V toolchain with `litex_setup.py`, or use an environment like [TimVideos LiteX BuildEnv](https://github.com/timvideos/litex-buildenv/) which provides precompiled toolchain for all three architectures.

Note: RISC-V toolchains support or require various extensions. Generally `rv32i` is used on smaller FPGAs, and `rv32im` on larger FPGAs -- the `rv32im` adds hardware multiplication and division (see [RISC V ISA base and extensions on Wikipedia](https://en.wikipedia.org/wiki/RISC-V#ISA_base_and_extensions) for more detail).

---

# SoftCPU options

The notes below provide extra background for some common soft CPUs. They are not intended to be an exhaustive list of all CPU wrappers; use the summary above or the LiteX CPU registry for the current complete list.

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

## [mor1kx - OpenRISC](https://github.com/openrisc/mor1kx)

An [OpenRISC 1000](https://openrisc.io/or1k.html) soft core (see also [Open RISC on Wikipedia](https://en.wikipedia.org/wiki/OpenRISC)).

### CPU Variants

 * standard
 * standard+fpu
 * linux
 * linux+fpu
 * linux+smp
 * linux+smp+fpu

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
 * minimal+debug
 * minimal+debug+hwbp
 * lite
 * lite+debug
 * lite+debug+hwbp
 * standard
 * standard+debug
 * imac
 * imac+debug
 * full
 * full+cfu
 * full+debug
 * full+cfu+debug
 * linux
 * linux+debug
 * linux+no-dsp
 * secure
 * secure+debug

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

The Minerva is a CPU core that currently implements the RISC-V RV32I instruction set with its microarchitecture described in plain Python code using the [nMigen toolbox](https://github.com/m-labs/nmigen).

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

## RISC-V - [`rocket`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/rocket)

The Rocket Chip is a full-featured, configurable CPU core that implements up to the full RISC-V RV64IMAFDC (a.k.a. RV64GC) instruction set, with its microarchitecture described in [Chisel](https://github.com/freechipsproject/chisel3).

### CPU Variants

 * small
 * medium
 * linux (`rv64imac` with enabled hardware MMU)
 * full (`rv64imafdc` with enabled hardware MMU and FPU)

### Tooling support

 * Upstream GCC
 * Upstream Binutils
 * Upstream clang

### OS support

 * Full upstream Linux support (for models with MMU enabled)

### Community

 * [Lots of activity](https://github.com/chipsalliance/rocket-chip)
 * Reference design for several taped-out ASICs (e.g., from [SiFive](https://www.sifive.com/risc-v-core-ip))

## RISC-V - [`neorv32`](https://github.com/enjoy-digital/litex/tree/master/litex/soc/cores/cpu/neorv32)

The [NEORV32 RISC-V Processor](https://github.com/stnolting/neorv32) is a tiny, customizable and highly extensible MCU-class 32-bit RISC-V soft-core CPU and microcontroller-like SoC written in platform-independent VHDL.

### CPU Variants

 * minimal (`rv32i_Zicsr_Zifencei`)
 * minimal+debug
 * lite (`rv32imc_Zicsr_Zifencei`)
 * lite+debug
 * standard (`rv32imc_Zicsr_Zifencei_Zicntr` + i-cache, fast MUL (DSPs) and barrel-shifter)
 * standard+debug
 * full (`rv32imcu_Zicsr_Zifencei_Zicntr_Zihpm` + i-cache + physical memory protection, fast MUL (DSPs) and barrel-shifter)
 * full+debug
 * numa
 * numa+debug

### Tooling support

 * Upstream GCC
 * Upstream Binutils
 * Upstream openOCD and GDB

### OS support

 * Upstream [Zephyr](https://docs.zephyrproject.org/latest/boards/riscv/neorv32/doc/index.html) support
 * FreeRTOS [port](https://github.com/stnolting/neorv32/tree/main/sw/example/demo_freeRTOS)

### Community

 * [gitter channel](https://gitter.im/neorv32/community)
 * community-driven [example setups and projects](https://github.com/stnolting/neorv32-setups) for various FPGAs, boards and toolchains
