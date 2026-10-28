The soft CPUs LiteX supports, by family, with their variants and where their sources come from:
thirty-two of them, plus the [hard CPUs](Hard-core-CPUs.md) and the QEMU emulator. `--cpu-type`
picks one, `--cpu-variant` its configuration, and the same SoC, BIOS and firmware build for all
of them, since the wrapper (`litex/soc/cores/cpu/<name>/core.py`) carries the memory map, the
compiler flags and the software support. The list is the one of 2026-10-28; your checkout
prints its own:

```sh
python3 -c "from litex.soc.cores.cpu import CPUS; print('\n'.join(sorted(k for k in CPUS if k)))"
```

[Choosing a CPU](Choosing-A-CPU.md) says which one to pick; this page is the catalog.
`--cpu-type=None` builds a SoC without CPU.

## Linux-capable RISC-V

The Linux line of LiteX: pick from the first column, `vexriscv_smp` being the mature 32-bit
choice and `vexiiriscv` the current 64-bit one.

| `--cpu-type` | ISA | Good for |
| --- | --- | --- |
| `vexriscv_smp` | RV32IMA[FD], MMU | Linux-on-LiteX-VexRiscv: 1 to 8 cores, coherent DMA, JTAG debug. |
| `naxriscv` | RV32/RV64 IMA[FD]C, MMU, out-of-order | Linux, 64-bit, superscalar; JTAG debug. |
| `vexiiriscv` | RV32/RV64 IMA[FD]C[B], MMU | The successor: configurable pipeline, Linux and Debian, Zephyr. |
| `rocket` | RV64IMA[FD]C, MMU | Upstream Linux (Linux-on-LiteX-Rocket); heavy: a large FPGA. |
| `cva6` | RV64GC or RV32, MMU | OpenHW application-class core; JTAG debug. |
| `openc906` | RV64GCV, MMU | T-Head XuanTie C906; JTAG debug. |
| `blackparrot` | RV64IMAFDC, MMU | Linux-capable multicore host. |
| `vexriscv` (`linux`) | RV32IMA, MMU | The historical single-core Linux configuration. |

<details>
<summary>Variants, options and sources</summary>

- **vexriscv_smp** ([VexRiscv](https://github.com/SpinalHDL/VexRiscv)): `standard`, `linux`; options
  `--cpu-count`, `--with-fpu`, `--with-rvc`, `--dcache-*`, `--icache-*`, `--with-coherent-dma`,
  `--with-privileged-debug`, `--hardware-breakpoints`. Wishbone plus direct memory buses.
  pythondata-cpu-vexriscv_smp, SpinalHDL, generated with sbt at build time.
- **naxriscv** ([NaxRiscv](https://github.com/SpinalHDL/NaxRiscv)): `standard`; options `--xlen 64`,
  `--cpu-count`, `--with-fpu`, `--with-rvc`, `--l2-bytes`, `--with-jtag-tap`. AXI-Lite plus
  direct memory buses. pythondata-cpu-naxriscv and the SpinalHDL repository, generated at build time.
- **vexiiriscv** ([VexiiRiscv](https://github.com/SpinalHDL/VexiiRiscv)): `standard`, `cached`,
  `linux`, `debian`; options `--vexii-args`, `--with-isa`, `--with-aia`. AXI-Lite plus direct
  memory buses. pythondata-cpu-vexiiriscv and the SpinalHDL repository, generated at build time.
- **rocket** ([Rocket Chip](https://github.com/chipsalliance/rocket-chip)): `small`, `medium`,
  `linux`, `full`; options `--cpu-num-cores`, `--cpu-mem-width`. AXI plus a 64/128-bit memory
  bus; reset at `0x10000000`. pythondata-cpu-rocket, Chisel, pre-generated.
- **cva6** ([CVA6](https://github.com/openhwgroup/cva6)): `standard`, `standard32`, `full`. AXI.
  pythondata-cpu-cva6, SystemVerilog.
- **openc906** ([OpenC906](https://github.com/T-head-Semi/openc906)): `standard`. AXI.
  pythondata-cpu-openc906, Verilog.
- **blackparrot** ([BlackParrot](https://github.com/black-parrot/black-parrot)): `standard`, `sim`.
  Wishbone; reset at `0x70000000`. pythondata-cpu-blackparrot, SystemVerilog.
- **vexriscv** (`linux` variant): see below.

</details>

## MCU-class RISC-V

For the BIOS, bare-metal firmware and an RTOS; `vexriscv` is the default of every SoC.

| `--cpu-type` | ISA | Good for |
| --- | --- | --- |
| `vexriscv` | RV32I[MAC] | The default: small, fast, the best supported (BIOS, Zephyr, JTAG debug, CFU). |
| `neorv32` | RV32I[MC][U], PMP | An MCU with its own peripherals and documentation; Zephyr, FreeRTOS, OpenOCD. |
| `ibex` | RV32IMC | lowRISC's MCU-class core. |
| `cv32e40p`, `cv32e41p` | RV32IMC[F] | OpenHW MCU-class cores with a debug module. |
| `cva5` | RV32IM[A][FD] | OpenHW, multicore with CLINT and PLIC, Wishbone or AXI. |
| `veer_eh1` | RV32IMC | Western Digital's core; many `--veer-*` options; JTAG debug. |
| `picorv32` | RV32IMC | Small, slow, robust. |
| `coreblocks` | RV32I[MAC], out-of-order | Written in Amaranth (Python 3.13 to elaborate). |
| `minerva` | RV32IM | Written in Amaranth, converted by LiteX. |
| `kianv` | RV32IMA | Linux in its own SoC, bare metal in LiteX. |
| `urv` | RV32IM | CERN's small core (White Rabbit). |
| `firev` | RV32I | The Silice example core. |

<details>
<summary>Variants, options and sources</summary>

- **vexriscv** ([VexRiscv](https://github.com/SpinalHDL/VexRiscv)): `minimal`, `lite`, `standard`,
  `imac`, `full`, `linux`, `secure`, with `+debug`, `+hwbp`, `+cfu`, `+no-dsp`. Wishbone.
  pythondata-cpu-vexriscv, SpinalHDL, one pre-generated netlist per variant.
- **neorv32** ([NEORV32](https://github.com/stnolting/neorv32)): `minimal`, `lite`, `standard`,
  `full`, `numa`, each with `+debug`; `--cpu-count`. Wishbone. VHDL downloaded at build time
  and converted with GHDL.
- **ibex** ([Ibex](https://github.com/lowRISC/ibex)): `standard`. Wishbone. pythondata-cpu-ibex, SystemVerilog.
- **cv32e40p**, **cv32e41p** ([CV32E40P](https://github.com/openhwgroup/cv32e40p)): `standard`,
  `standard+fpu` (E40P). Wishbone. pythondata-cpu-cv32e40p and cv32e41p, SystemVerilog.
- **cva5** ([CVA5](https://github.com/openhwgroup/cva5)): `minimal`, `standard`, `standard+atomic`,
  `standard+atomic+float+double`; `--cpu-count`, `--bus-type`. pythondata-cpu-cva5, SystemVerilog.
- **veer_eh1** ([VeeR EH1](https://github.com/chipsalliance/Cores-VeeR-EH1)): `standard`. AXI.
  pythondata-cpu-veer-eh1, SystemVerilog.
- **picorv32** ([PicoRV32](https://github.com/YosysHQ/picorv32)): `minimal`, `standard`. Wishbone.
  pythondata-cpu-picorv32, Verilog.
- **coreblocks** ([Coreblocks](https://github.com/kuznia-rdzeni/coreblocks)): `standard`,
  `small_linux`, `full`. Wishbone. pythondata-cpu-coreblocks, Amaranth.
- **minerva** ([Minerva](https://github.com/minerva-cpu/minerva)): `standard`. Wishbone.
  pythondata-cpu-minerva and amaranth-soc, elaborated at build time.
- **kianv** ([KianV](https://github.com/splinedrive/kianRiscV)), **urv** ([uRV](https://ohwr.org/project/urv-core)),
  **firev** ([Fire-V](https://github.com/sylefeb/Silice)): `standard`. Wishbone. Cloned or
  downloaded at build time; Verilog, Verilog, Silice.

</details>

## Tiny RISC-V

For the BIOS and control firmware on the smallest FPGAs; no MMU, a few hundred LUTs.

| `--cpu-type` | ISA | Good for |
| --- | --- | --- |
| `serv` | RV32I, bit-serial | The smallest RISC-V there is. |
| `fazyrv` | RV32I/E, chunked | Between bit-serial and full width, the chunk size is yours. |
| `femtorv` | RV32I/M/F | Bruno Levy's teaching cores, from `quark` to the FPU-equipped `petitbateau`. |
| `sentinel` | RV32I, microcoded | A very small microcoded core in Amaranth. |

<details>
<summary>Variants, options and sources</summary>

- **serv** ([SERV](https://github.com/olofk/serv)): `standard`, `mdu`. pythondata-cpu-serv, Verilog.
- **fazyrv** ([FazyRV](https://github.com/meiniKi/FazyRV)): `standard`; `--cpu-chunksize`,
  `--cpu-rftype`, `--cpu-rvc`. Cloned at build time, Verilog.
- **femtorv** ([FemtoRV](https://github.com/BrunoLevy/learn-fpga)): `standard`, `quark`, `tachyon`,
  `electron`, `intermissum`, `gracilis`, `petitbateau`. Downloaded at build time, Verilog.
- **sentinel** ([Sentinel](https://github.com/cr1901/sentinel)): `standard`. pythondata-cpu-sentinel
  and amaranth-soc, Amaranth.

</details>

## Other ISAs

| `--cpu-type` | ISA | Good for |
| --- | --- | --- |
| `mor1kx` | OpenRISC 1000 | Upstream Linux, SMP and FPU variants. |
| `marocchino` | OpenRISC 1000, out-of-order | Linux, SMP. |
| `lm32` | LatticeMico32 | The original MiSoC CPU; bare metal. |
| `microwatt` | POWER (ppc64le) | The OpenPOWER core in VHDL, upstream Linux. |
| `cdim`, `gs232` | MIPS32 | CQU CDIM and Loongson GS232; Linux boot covered in CI. |
| `cortex_m1`, `cortex_m3` | ARMv6-M, ARMv7-M | Arm DesignStart, with RTL you download yourself. |

<details>
<summary>Variants, options and sources</summary>

- **mor1kx** ([mor1kx](https://github.com/openrisc/mor1kx)): `standard`, `standard+fpu`, `linux`,
  `linux+fpu`, `linux+smp`, `linux+smp+fpu`. pythondata-cpu-mor1kx, Verilog. Big-endian.
- **marocchino** ([Marocchino](https://github.com/openrisc/or1k_marocchino)): `standard`, `linux`,
  `linux+smp`. pythondata-cpu-marocchino, Verilog.
- **lm32** ([LatticeMico32](https://github.com/m-labs/lm32)): `minimal`, `lite`, `standard`.
  pythondata-cpu-lm32, Verilog. Big-endian; GCC from the `litex-hub` conda channel.
- **microwatt** ([Microwatt](https://github.com/antonblanchard/microwatt)): `standard`,
  `standard+ghdl`, `standard+irq`, `standard+ghdl+irq`. pythondata-cpu-microwatt, VHDL (GHDL
  plugin or conversion).
- **cdim**, **gs232**: `standard`. AXI; reset at `0x1fc00000`; `--gcc=mips`. pythondata-cpu-cdim
  and gs232, Verilog.
- **cortex_m1**, **cortex_m3**: `standard` (M3: `generic`). AXI. Proprietary DesignStart RTL,
  not redistributed: `--cpu-rtl-dir`.

</details>

## Emulator and CI

`--cpu-type=qemu` runs the CPU in a patched QEMU (`rv32` and `rv64` variants) while the rest of
the SoC runs in Verilator ([QEMU co-simulation](SoC-Simulator.md#qemu-co-simulation)).

CI boots the BIOS in `litex_sim` on blackparrot, cdim, coreblocks, cv32e40p, cv32e41p, cva6,
femtorv, firev, gs232, ibex, lm32, marocchino, microwatt, minerva, mor1kx, naxriscv, neorv32,
picorv32, sentinel, serv, vexiiriscv, vexriscv and vexriscv_smp; cva5 (a Verilator limitation)
and rocket (memory) are built but not booted, the hard CPUs and the Cortex-M cannot be.

## Compilers

- RISC-V: `litex_setup.py --gcc=riscv` installs the distribution's `riscv64-unknown-elf-gcc`
  (`riscv64-linux-gnu-gcc` and `riscv-none-elf-gcc` are accepted too); clang works for the
  32-bit cores.
- OpenRISC: `--gcc=openrisc` (`or1k-elf-gcc`, upstream GCC since 9).
- LM32: `--gcc=lm32` from the `litex-hub` conda channel (upstream GCC, no clang).
- POWER: `--gcc=powerpc` (`powerpc64le-linux-gnu-gcc`); MIPS: `--gcc=mips` (`mipsel-linux-gnu-gcc`).
- Arm: the Cortex-M cores use `arm-none-eabi-gcc`.

The `rv32i`, `rv32im` or `rv32imac` choice is made by the variant: `minimal` cores omit the
multiplier and the compressed instructions, which is why a `-march` mismatch between the
firmware and the CPU shows as an illegal instruction trap.

## Next

- [Choosing a CPU](Choosing-A-CPU.md): which one, the variants, how a CPU is integrated.
- [Hard core CPUs](Hard-core-CPUs.md): the seven hard CPUs.
- [Add a new CPU](Add-A-New-CPU.md): a wrapper of your own.
- [Run Linux on your SoC](Run-Linux-On-Your-SoC.md): the Linux-capable ones in practice.
