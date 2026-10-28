`--cpu-type=<name>` selects the CPU and `--cpu-variant=<variant>` its configuration; the same
SoC, BIOS and firmware build for every one of them, since LiteX provides the wrapper, the
memory map, the compiler flags and the software support (`litex/soc/cores/cpu/<name>/core.py`).
The list below is the one of `litex/soc/cores/cpu/` on 2026-10-27; the current registry of a
checkout is printed by:

```sh
python3 -c "from litex.soc.cores.cpu import CPUS; print('\n'.join(sorted(str(k) for k in CPUS if k is not None)))"
```

`--cpu-type=None` is also supported for SoCs without an embedded CPU.

[Choosing a CPU](Choosing-A-CPU.md) helps picking one and describes the variants and the
integration; this page is the catalog.

## Soft CPUs

| `--cpu-type` | CPU | ISA | Bus | Variants | Sources, language | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `vexriscv` | [VexRiscv](https://github.com/SpinalHDL/VexRiscv) | RV32I[MAC] | Wishbone | `minimal`, `lite`, `standard`, `imac`, `full`, `linux`, `secure`, with `+debug`, `+hwbp`, `+cfu`, `+no-dsp` | pythondata-cpu-vexriscv (pre-generated Verilog per variant), SpinalHDL | The default CPU: small, fast, the best supported (BIOS, Zephyr, Linux with the `linux` variant, JTAG debug, CFU). |
| `vexriscv_smp` | [VexRiscv SMP](https://github.com/SpinalHDL/VexRiscv) | RV32IMA[FD], MMU | Wishbone + direct memory buses | `standard`, `linux` (+ `--cpu-count`, `--with-fpu`, `--with-rvc`, `--dcache-*`, `--icache-*`, `--with-coherent-dma`, `--with-privileged-debug`, `--hardware-breakpoints`...) | pythondata-cpu-vexriscv_smp (generated with sbt at build time), SpinalHDL | Linux-on-LiteX-VexRiscv: 1 to 8 cores, coherent DMA bus, JTAG debug. |
| `naxriscv` | [NaxRiscv](https://github.com/SpinalHDL/NaxRiscv) | RV32/RV64 IMA[FD]C, MMU, out-of-order | AXI-Lite + direct memory buses | `standard` (+ `--xlen 64`, `--cpu-count`, `--with-fpu`, `--with-rvc`, `--l2-bytes`, `--with-jtag-tap`...) | pythondata-cpu-naxriscv + the SpinalHDL repository, generated at build time | Out-of-order, superscalar; Linux (64-bit); JTAG debug. |
| `vexiiriscv` | [VexiiRiscv](https://github.com/SpinalHDL/VexiiRiscv) | RV32/RV64 IMA[FD]C[B], MMU | AXI-Lite + direct memory buses | `standard`, `cached`, `linux`, `debian` (+ `--vexii-args`, `--with-isa`, `--with-aia`...) | pythondata-cpu-vexiiriscv + the SpinalHDL repository, generated at build time | The successor of VexRiscv/NaxRiscv: configurable pipeline, Linux and Debian, JTAG debug; Zephyr `litex_vexiiriscv` board. |
| `rocket` | [Rocket Chip](https://github.com/chipsalliance/rocket-chip) | RV64IMA[FD]C, MMU | AXI + 64/128-bit memory bus | `small`, `medium`, `linux`, `full` (+ `--cpu-num-cores`, `--cpu-mem-width`) | pythondata-cpu-rocket (pre-generated), Chisel | Upstream Linux (Linux-on-LiteX-Rocket); reset at `0x10000000`. |
| `cva6` | [CVA6](https://github.com/openhwgroup/cva6) | RV64GC or RV32 (`standard32`), MMU | AXI | `standard`, `standard32`, `full` | pythondata-cpu-cva6, SystemVerilog | OpenHW application-class core; JTAG debug. |
| `cva5` | [CVA5](https://github.com/openhwgroup/cva5) | RV32IM[A][FD] | Wishbone or AXI (`--bus-type`) | `minimal`, `standard`, `standard+atomic`, `standard+atomic+float+double` (+ `--cpu-count`) | pythondata-cpu-cva5, SystemVerilog | OpenHW, multi-core with CLINT/PLIC. |
| `cv32e40p`, `cv32e41p` | [CV32E40P/E41P](https://github.com/openhwgroup/cv32e40p) | RV32IMC[F] | Wishbone | `standard`, `standard+fpu` (E40P) | pythondata-cpu-cv32e40p/41p, SystemVerilog | OpenHW MCU-class cores with a debug module. |
| `ibex` | [Ibex](https://github.com/lowRISC/ibex) | RV32IMC | Wishbone | `standard` | pythondata-cpu-ibex, SystemVerilog | lowRISC MCU-class core. |
| `neorv32` | [NEORV32](https://github.com/stnolting/neorv32) | RV32I[MC][U], PMP | Wishbone | `minimal`, `lite`, `standard`, `full`, `numa`, each `+debug` (+ `--cpu-count`) | VHDL downloaded at build time (GHDL conversion) | MCU-class with its own peripherals, Zephyr, FreeRTOS, OpenOCD/GDB. |
| `picorv32` | [PicoRV32](https://github.com/YosysHQ/picorv32) | RV32IMC | Wishbone | `minimal`, `standard` | pythondata-cpu-picorv32, Verilog | Small, slow, robust. |
| `serv` | [SERV](https://github.com/olofk/serv) | RV32I (bit-serial) | Wishbone | `standard`, `mdu` | pythondata-cpu-serv, Verilog | The smallest RISC-V: a few hundred LUTs. |
| `fazyrv` | [FazyRV](https://github.com/meiniKi/FazyRV) | RV32I/E (chunked) | Wishbone | `standard` (+ `--cpu-chunksize`, `--cpu-rftype`, `--cpu-rvc`) | cloned at build time, Verilog | Between bit-serial and full width. |
| `femtorv` | [FemtoRV](https://github.com/BrunoLevy/learn-fpga) | RV32I/M/F | Wishbone | `standard`, `quark`, `tachyon`, `electron`, `intermissum`, `gracilis`, `petitbateau` | downloaded at build time, Verilog | Bruno Levy's teaching cores, from tiny to FPU. |
| `firev` | [Fire-V](https://github.com/sylefeb/Silice) | RV32I | Wishbone | `standard` | downloaded at build time, Silice | Silice example core. |
| `kianv` | [KianV](https://github.com/splinedrive/kianRiscV) | RV32IMA | Wishbone | `standard` | cloned at build time, Verilog | Linux-capable in its own SoC; bare metal in LiteX. |
| `urv` | [uRV](https://ohwr.org/project/urv-core) | RV32IM | Wishbone | `standard` | cloned at build time (OHWR), Verilog | CERN's small core (White Rabbit). |
| `minerva` | [Minerva](https://github.com/minerva-cpu/minerva) | RV32IM | Wishbone | `standard` | pythondata-cpu-minerva + amaranth-soc, Amaranth (elaborated at build time) | Written in Amaranth, converted to Verilog by LiteX. |
| `sentinel` | [Sentinel](https://github.com/cr1901/sentinel) | RV32I (microcoded) | Wishbone | `standard` | pythondata-cpu-sentinel + amaranth-soc, Amaranth | Very small microcoded core. |
| `coreblocks` | [Coreblocks](https://github.com/kuznia-rdzeni/coreblocks) | RV32I[M][A][C][ZbaZbbZbcZbs], out-of-order | Wishbone (ibus/dbus) | `standard`, `small_linux`, `full` | pythondata-cpu-coreblocks, Amaranth (needs Python 3.13 to elaborate) | Out-of-order core from Kuźnia Rdzeni. |
| `veer_eh1` | [VeeR EH1](https://github.com/chipsalliance/Cores-VeeR-EH1) | RV32IMC | AXI (ibus/dbus) | `standard` (+ many `--veer-*` options) | pythondata-cpu-veer-eh1, SystemVerilog | Western Digital/CHIPS Alliance core; JTAG debug. |
| `openc906` | [OpenC906](https://github.com/T-head-Semi/openc906) | RV64GCV, MMU | AXI | `standard` | pythondata-cpu-openc906, Verilog | T-Head XuanTie C906; JTAG debug. |
| `blackparrot` | [BlackParrot](https://github.com/black-parrot/black-parrot) | RV64IMAFDC, MMU | Wishbone | `standard`, `sim` | pythondata-cpu-blackparrot, SystemVerilog | Linux-capable multicore host; reset at `0x70000000`. |
| `microwatt` | [Microwatt](https://github.com/antonblanchard/microwatt) | POWER (ppc64le) | Wishbone | `standard`, `standard+ghdl`, `standard+irq`, `standard+ghdl+irq` | pythondata-cpu-microwatt, VHDL (GHDL plugin or conversion) | OpenPOWER; Linux upstream. |
| `mor1kx` | [mor1kx](https://github.com/openrisc/mor1kx) | OpenRISC 1000 (big-endian) | Wishbone | `standard`, `standard+fpu`, `linux`, `linux+fpu`, `linux+smp`, `linux+smp+fpu` | pythondata-cpu-mor1kx, Verilog | Linux upstream. |
| `marocchino` | [Marocchino](https://github.com/openrisc/or1k_marocchino) | OpenRISC 1000, out-of-order | Wishbone | `standard`, `linux`, `linux+smp` | pythondata-cpu-marocchino, Verilog | |
| `lm32` | [LatticeMico32](https://github.com/m-labs/lm32) | LM32 (big-endian) | Wishbone | `minimal`, `lite`, `standard` | pythondata-cpu-lm32, Verilog | The original MiSoC CPU; GCC from the `litex-hub` conda channel. |
| `cdim`, `gs232` | CQU CDIM, Loongson GS232 | MIPS32 | AXI | `standard` | pythondata-cpu-cdim / gs232, Verilog | MIPS cores (`--gcc=mips`); reset at `0x1fc00000`; Linux boot covered in CI for both. |
| `cortex_m1`, `cortex_m3` | Arm Cortex-M1/M3 DesignStart | ARMv6-M / ARMv7-M | AXI | `standard` (M3: `generic`) | Arm DesignStart RTL, to be downloaded by the user (`--cpu-rtl-dir`) | Proprietary RTL, not redistributed. |

The `emulator` category has `qemu`: the CPU runs in a patched QEMU (`rv32`/`rv64` variants) while
the rest of the SoC runs in Verilator ([QEMU co-simulation](SoC-Simulator.md#qemu-co-simulation)).

CI boots the BIOS in `litex_sim` on: blackparrot, cdim, coreblocks, cv32e40p, cv32e41p, cva6,
femtorv, firev, gs232, ibex, lm32, marocchino, microwatt, minerva, mor1kx, naxriscv, neorv32,
picorv32, sentinel, serv, vexiiriscv, vexriscv, vexriscv_smp; cva5 (Verilator limitation) and
rocket (memory) are built but not booted in CI, the hard CPUs and the proprietary Cortex-M
cannot be.

## Compilers

- RISC-V: `litex_setup.py --gcc=riscv` installs the distribution's `riscv64-unknown-elf-gcc`
  (`riscv64-linux-gnu-gcc` and `riscv-none-elf-gcc` are accepted too); clang works for the
  32-bit cores.
- OpenRISC: `--gcc=openrisc` (`or1k-elf-gcc`, upstream GCC since 9).
- LM32: `--gcc=lm32` from the `litex-hub` conda channel (upstream GCC, no clang).
- POWER: `--gcc=powerpc` (`powerpc64le-linux-gnu-gcc`); MIPS: `--gcc=mips` (`mipsel-linux-gnu-gcc`).
- Arm: the Cortex-M cores use `arm-none-eabi-gcc`.

The `rv32i`/`rv32im`/`rv32imac` choice is made by the variant: `minimal` cores omit the
multiplier and the compressed instructions, which is why a `-march` mismatch between the
firmware and the CPU shows as an illegal instruction trap.

## Notes on common CPUs

### VexRiscv

The default CPU of LiteX and the most used: an in-order 5-stage RV32 pipeline written in
SpinalHDL, from ~1000 LUTs (`minimal`) to a Linux-capable MMU configuration (`linux`),
with caches, hardware breakpoints, JTAG debug (`+debug`), a CFU interface (`+cfu`) and a
`secure` variant with PMP. Upstream Zephyr (`litex_vexriscv`), Linux through
[Linux-on-LiteX-VexRiscv](https://github.com/litex-hub/linux-on-litex-vexriscv) (which uses
`vexriscv_smp`), the BIOS everywhere. Lots of activity, the reference for new features.

### VexRiscv SMP, NaxRiscv, VexiiRiscv

The SpinalHDL family for Linux: `vexriscv_smp` (32-bit, 1 to 8 cores, FPU, coherent DMA) is
the mature one; `naxriscv` is out-of-order and 64-bit capable; `vexiiriscv` is the current
generation with a configurable pipeline, 64-bit, Linux and Debian, and the best performance
per LUT. All three are generated at build time (sbt, cached netlists) with the options of the
target.

### Rocket

The Chisel RV64GC core of the Berkeley/SiFive lineage: `small`/`medium` without MMU, `linux`
(rv64imac + MMU) and `full` (rv64imafdc + MMU + FPU), several cores with `--cpu-num-cores`,
a wide memory bus to LiteDRAM; upstream Linux through
[Linux-on-LiteX-Rocket](https://github.com/litex-hub/linux-on-litex-rocket). Heavy: a large
Artix-7/ECP5 or an UltraScale.

### NEORV32

A VHDL MCU-class RISC-V with its own peripherals and documentation, converted to Verilog by
LiteX with GHDL: `minimal` (`rv32i_Zicsr_Zifencei`) to `full` (`rv32imcu` with counters,
PMP, caches), `+debug` for the on-chip debugger (OpenOCD/GDB), upstream Zephyr and a FreeRTOS
port, `numa` for several cores.

### PicoRV32, SERV, FemtoRV, FazyRV, Minerva, Sentinel

The small ones: PicoRV32 (robust, slow, `rv32imc`), SERV (bit-serial, the smallest), FemtoRV
(a family from `quark` to the FPU-equipped `petitbateau`, written for teaching), FazyRV
(configurable chunk size), Minerva and Sentinel (written in Amaranth). For the BIOS and
bare-metal control firmware on the smallest FPGAs; no MMU.

### mor1kx, Marocchino, LM32, Microwatt

The non-RISC-V soft cores: the OpenRISC cores with upstream Linux (and SMP, FPU variants),
LatticeMico32 (the historical MiSoC CPU, bare metal and an old NuttX), and Microwatt, the
OpenPOWER core in VHDL with upstream Linux.
