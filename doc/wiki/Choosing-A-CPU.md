LiteX can create SoCs with or without CPU. Some simple SoCs don't use any CPU (bridging SoCs for
example), some SoCs use a CPU but external to the FPGA (PCIe SoCs for example where the CPU is
directly the CPU of the Host machine) but in most of the cases the SoC embeds a CPU to control
the system and/or ease splitting tasks between software/hardware: a *soft* CPU synthesized in
the fabric, or the *hard* CPU of a SoC-FPGA ([Hard core CPUs](Hard-core-CPUs.md)).

[CPUs](CPUs.md) is the catalog of the soft CPUs; this page helps you pick one and says
how a CPU fits in the SoC.

## By need

- **A controller for your cores, a BIOS, bare-metal firmware or an RTOS:** `vexriscv`
  (`standard`, or `lite`/`minimal` on small FPGAs), `neorv32` for its MCU peripherals and
  Zephyr support, `serv`/`fazyrv`/`femtorv quark` when every LUT counts.
- **Linux:** `vexriscv_smp` (the reference, 32-bit, up to 8 cores), `vexiiriscv` or
  `naxriscv` (64-bit, more performance), `rocket` and `cva6` (64-bit, upstream kernels),
  `mor1kx`/`marocchino` (OpenRISC), `microwatt` (POWER), the hard CPUs.
- **Floating point:** `vexriscv_smp --with-fpu`, `naxriscv --with-fpu`, `vexiiriscv`,
  `rocket full`, `cva6`, `cva5 standard+atomic+float+double`, `cv32e40p standard+fpu`,
  `femtorv petitbateau`.
- **Debugging with GDB over JTAG:** `vexriscv +debug`, `vexriscv_smp`, `naxriscv`,
  `vexiiriscv`, `neorv32 +debug`, `cva6`, `veer_eh1`, `openc906`
  ([JTAG/GDB debugging](Debug-With-GDB.md)).
- **A custom instruction (CFU):** `vexriscv full+cfu` with `--cpu-cfu=<verilog>`
  ([CFU Playground](https://github.com/google/CFU-Playground)).

## Variants

Most CPUs have several configurations: `--cpu-variant` selects one and the names are CPU
specific (the wrapper's `variants` list, printed in the error message when a name is wrong).
Common names: `minimal` (the smallest working configuration, often without exceptions),
`lite` (bare metal and RTOS on small FPGAs: iCE40, small ECP5/Artix-7), `standard` (the
default, bare metal and RTOS on modern FPGAs), `full` (every feature), `linux` (MMU,
supervisor mode, what Linux needs). Extensions are suffixed with `+`: `+debug` (the debug
port), `+fpu`, `+smp`, `+cfu`, `+irq`, `+ghdl`... Each combination is a key of the CPU's list,
there is no generic combinator: `vexriscv` has `standard+debug` but `serv` has no `+debug`.

| Variant | CPUs |
| --- | --- |
| `minimal` | cva5, lm32, neorv32, picorv32, vexriscv |
| `lite` | lm32, neorv32, vexriscv |
| `standard` | all |
| `full` | coreblocks, cva6, neorv32, rocket, vexriscv |
| `linux` | coreblocks (`small_linux`), gowin_ae350, marocchino, mor1kx, rocket, vexiiriscv, vexriscv, vexriscv_smp (naxriscv is always Linux capable, `--xlen 64`) |
| `+debug` | neorv32, vexriscv (`+hwbp` for hardware breakpoints) |
| `+fpu` / float | cv32e40p, mor1kx, cva5 (`+float+double`), vexriscv_smp/naxriscv (`--with-fpu`) |
| `+smp` / multi-core | mor1kx, marocchino; vexriscv_smp, naxriscv, cva5, neorv32 (`--cpu-count`), rocket (`--cpu-num-cores`) |

The generated CPUs (vexriscv_smp, naxriscv, vexiiriscv) take their configuration from
command-line options instead of variants (`python3 target.py --cpu-type=vexiiriscv --help`
shows them); the pre-generated ones (vexriscv, rocket) ship one netlist per variant in their
pythondata package.

## How a CPU is integrated

`soc.add_cpu(name, variant, reset_address)` (called by `SoCCore`) does the same for every
wrapper:

- its **peripheral buses** (`periph_buses`: instruction and data Wishbone, or AXI/AXI-Lite)
  become masters of the main bus, adapted to the bus standard and width of the SoC;
- its **memory buses** (`memory_buses`, on VexRiscv-SMP, NaxRiscv, VexiiRiscv, Rocket, AE350)
  are connected straight to the LiteDRAM crossbar by `add_sdram`, bypassing the main bus;
- its **DMA bus** (`dma_bus`, coherent on VexRiscv-SMP/NaxRiscv/VexiiRiscv) is a slave port
  for the DMAs of the cores so that Linux sees coherent memory;
- its **IO regions** (`io_regions`, `0x80000000-0xffffffff` on most 32-bit cores) tell the
  SoC where uncached peripherals can live, and its **`mem_map`** overrides the default origins
  (`rom`, `sram`, `main_ram`, `csr`);
- its **reset address** defaults to the ROM origin (the BIOS), `--cpu-reset-address` moves it
  (flash, main RAM); some CPUs impose it (Rocket, CVA6 `0x10000000`, BlackParrot `0x70000000`,
  MIPS `0x1fc00000`);
- its **interrupts** (`interrupts` dict, `interrupt` signal) are wired to the IRQ handler and
  exported to `soc.h`;
- its **compiler flags** (`gcc_triple`, `gcc_flags`, `linker_output_format`) drive the BIOS
  and firmware build, and its `add_software_packages`/`prepare_software` hooks add CPU-specific
  software (the Zynq libxil BSP, the Rocket/NaxRiscv linker scripts...);
- `CPU_TYPE_<name>`, `CPU_VARIANT_<variant>`, `CPU_FAMILY`, `CPU_NAME`, `CPU_HUMAN_NAME`,
  `CPU_NOP`, `CPU_RESET_ADDR` constants are generated for the software.

[Add a new CPU](Add-A-New-CPU.md) describes a wrapper; `litex/soc/cores/cpu/picorv32/core.py`
is a good 150-line example, `vexriscv_smp/core.py` a generated one with options.
