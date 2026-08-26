# sim/qemu: add QEMU CPU co-simulation for LiteX SIM

## Purpose

This PR adds a prototype QEMU co-simulation mode for `litex_sim`: QEMU runs the
RISC-V CPU while the regular LiteX SoC, interconnect and peripherals remain in
Verilator.

The goal is to make CPU-heavy simulation workloads significantly faster without
losing LiteX's normal simulated peripheral model. This also provides a path for
Linux-oriented experiments where instruction execution should happen in QEMU,
while LiteX-specific MMIO and DMA-visible memory remain observable in the
Verilated SoC.

## Summary

- Add a `qemu` RISC-V CPU integration with RV32 and RV64 variants.
- Add bus-native litex_sim external modules that bridge QEMU MMIO accesses to
  Wishbone, AXI-Lite or AXI masters.
- Wire QEMU launch support into `litex_sim --cpu-type=qemu`, including automatic
  bridge readiness waiting.
- Add a QEMU `litex-sim` machine patch for QEMU v8.2.4 and document the bridge
  protocol.
- Add helper scripts to build/check the patched QEMU binaries.
- Add Linux boot asset plumbing for `-bios`, `-kernel`, `-dtb`, `-initrd` and
  `-append`.
- Add smoke helpers for RV32/RV64 and `wishbone`/`axi-lite`/`axi` SoC bus
  standards.
- Add a shared integrated main RAM backend so QEMU CPU accesses and Verilated
  LiteX DMA/peripheral accesses can target the same backing storage.
- Add a CI integration test that prepares patched RV32 QEMU and boots
  `litex_sim --cpu-type=qemu`.

## Design

QEMU owns CPU execution and local executable memory. LiteX/Verilator owns the
regular SoC MMIO/peripheral window. QEMU forwards MMIO accesses to a
Verilator-side bridge module over a small blocking TCP request/response
protocol.

The bridge module is selected from `--bus-standard`: `qemu_wishbone`,
`qemu_axi_lite` or `qemu_axi`. This keeps the QEMU CPU wrapper native to the
selected LiteX SoC bus instead of inserting a Wishbone conversion layer inside
the CPU integration. The QEMU protocol is still intentionally blocking and
single-access; the native AXI module maps each QEMU MMIO access to a single-beat
AXI transaction with ID 0.

When `--cpu-type=qemu` is used with integrated main RAM, `litex_sim` replaces
the generated LiteX RAM with `QEMUSharedRAM`. QEMU maps the same file through
`memory-backend-file`, while Verilator maps it through the bus-native shared RAM
module: `qemu_shared_ram`, `qemu_axi_lite_shared_ram` or
`qemu_axi_shared_ram`. This lets LiteX bus masters, including DMA-capable
peripherals, access the same main RAM storage as the QEMU CPU.

## User Flow

Build the patched QEMU binaries:

```sh
python3 litex/build/sim/qemu/build_qemu_litex.py
```

Run a basic QEMU-backed LiteX SIM:

```sh
python3 -m litex.tools.litex_sim \
  --cpu-type=qemu \
  --cpu-variant=rv32 \
  --integrated-main-ram-size=0x100000
```

Run RV64:

```sh
python3 -m litex.tools.litex_sim \
  --cpu-type=qemu \
  --cpu-variant=rv64 \
  --integrated-main-ram-size=0x100000
```

Check the patched QEMU binaries:

```sh
python3 litex/build/sim/qemu/check_qemu_litex.py
```

Check the LiteX bus-standard matrix:

```sh
python3 litex/build/sim/qemu/check_qemu_bus_matrix.py
```

## Notes And Limitations

- The bridge protocol is intentionally simple and blocking.
- The QEMU MMIO path currently generates blocking single-beat accesses.
- AXI-Lite and AXI are native at the sim-module pins, but the v1 QEMU protocol
  does not generate AXI bursts.
- Shared main RAM shares storage, not CPU cache state. Software using DMA still
  needs normal cache maintenance or uncached mappings.
- Linux boot plumbing is present, but a complete Linux target still needs
  matching firmware, DTB, timer and interrupt modeling.

## Validation

The branch was validated with:

```sh
git diff --check master..HEAD
git log --check --pretty=oneline master..HEAD
python3 -m py_compile \
  litex/tools/litex_sim.py \
  litex/soc/cores/cpu/qemu/core.py \
  litex/build/sim/qemu/build_qemu_litex.py \
  litex/build/sim/qemu/check_qemu_litex.py \
  litex/build/sim/qemu/check_qemu_bus_matrix.py
timeout 60s python3 -m litex.tools.litex_sim \
  --cpu-type=qemu \
  --cpu-variant=rv32 \
  --integrated-main-ram-size=0x100000 \
  --qemu-no-run \
  --no-compile \
  --output-dir=build/sim-shm-elab-rewrite
LITEX_QEMU_COSIM_TEST=1 python3 -m pytest -q \
  test/test_integration.py::test_qemu_cpu
```

Earlier smoke runs also built and launched the Verilator/QEMU pair for RV32 and
RV64 with shared integrated main RAM, reached the LiteX BIOS prompt, and passed
the BIOS main RAM memtest.
