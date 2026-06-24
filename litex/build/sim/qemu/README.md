# LiteX SIM QEMU Co-Simulation Bridge

This directory documents the QEMU-side contract used by `litex_sim --cpu-type=qemu`.
The LiteX repository does not contain QEMU sources, so the actual QEMU machine/device
has to be added to a QEMU checkout.

## Build Patched QEMU

The helper below clones QEMU `v8.2.4`, applies `qemu-litex-sim-v8.2.4.patch`,
builds the RV32/RV64 system emulators, and copies the binaries to
`build/qemu-litex/bin/`:

```sh
python3 litex/build/sim/qemu/build_qemu_litex.py
```

For CI or reproducible local builds without a QEMU git checkout, use the
official release archive:

```sh
python3 litex/build/sim/qemu/build_qemu_litex.py --source=archive
```

The resulting binaries can be passed directly to `litex_sim`:

```sh
python3 -m litex.tools.litex_sim \
  --cpu-type=qemu \
  --cpu-variant=rv32 \
  --qemu-binary build/qemu-litex/bin/qemu-system-riscv32
```

When the helper-installed binary exists, `litex_sim` will also find it
automatically for the selected RV32/RV64 variant.

RV64 is selected with `--cpu-variant=rv64`:

```sh
python3 -m litex.tools.litex_sim \
  --cpu-type=qemu \
  --cpu-variant=rv64
```

To only check that the patched machine is present:

```sh
python3 litex/build/sim/qemu/check_qemu_litex.py
```

## Linux Boot Smoke

`litex_sim` can pass Linux-oriented boot assets through to QEMU:

```sh
python3 -m litex.tools.litex_sim \
  --cpu-type=qemu \
  --cpu-variant=rv64 \
  --qemu-binary build/qemu-litex/bin/qemu-system-riscv64 \
  --qemu-firmware path/to/fw_dynamic.bin \
  --qemu-kernel path/to/Image \
  --qemu-dtb path/to/litex.dtb \
  --qemu-initrd path/to/rootfs.cpio \
  --qemu-append "console=liteuart earlycon"
```

The `litex-sim` QEMU machine provides the RISC-V local interrupt pieces Linux
expects: QEMU owns the ACLINT/CLINT timer/software interrupt block and the
SiFive-compatible PLIC, while LiteX/Verilator owns the SoC peripherals. The
bridge is mapped over the CPU IO window, so Linux can access non-CSR LiteX
windows such as LiteEth MAC buffers or framebuffer regions in addition to the
CSR window. Peripheral DMA to integrated main RAM requires the shared RAM path
described below.

## Shared Main RAM

When `--cpu-type=qemu` is used with `--integrated-main-ram-size`,
`litex_sim` now backs main RAM with a shared file by default. QEMU maps the
file with `memory-backend-file` and Verilator exposes the same file as the
LiteX `main_ram` slave through the bus-native QEMU simulation module.

This gives Verilated LiteX masters, including DMA-capable peripherals, a real
path to the same main RAM storage that QEMU uses for CPU accesses:

```sh
python3 -m litex.tools.litex_sim \
  --cpu-type=qemu \
  --cpu-variant=rv32 \
  --integrated-main-ram-size=0x100000
```

The default backing file is `<output-dir>/qemu-main-ram.bin`, so with the
default build directory it is `build/sim/qemu-main-ram.bin`. It is recreated
at simulation start and is preloaded from `--ram-init` when that option is
used. Use `--qemu-shared-ram-path` to choose another file:

```sh
python3 -m litex.tools.litex_sim \
  --cpu-type=qemu \
  --integrated-main-ram-size=0x100000 \
  --qemu-shared-ram-path=/tmp/litex-main-ram.bin
```

The shared RAM path still uses a simple 32-bit single-word access path to the
mapped backing file internally and exposes it as a `qemu_axi_shared_ram` full
AXI interface. LiteX adapts this interface when the SoC bus is AXI-Lite or
Wishbone. It shares storage, not cache management: software that mixes CPU caches and
peripheral DMA still needs the normal cache maintenance/uncached mapping
discipline.

## Bus Standards

The working bridge protocol is single-beat MMIO. The QEMU CPU wrapper exposes
a full AXI master and LiteX adapts it to the selected SoC `--bus-standard` when
needed:

```sh
python3 -m litex.tools.litex_sim \
  --cpu-type=qemu \
  --bus-standard=axi-lite \
  --qemu-no-run
```

The QEMU simulation module is always `qemu_axi`. The supported SoC bus
standards are `wishbone`, `axi-lite`, and `axi`. A quick build-time smoke can
elaborate one selection without launching QEMU or compiling generated
software/gateware:

```sh
python3 -m litex.tools.litex_sim \
  --cpu-type=qemu \
  --cpu-variant=rv32 \
  --bus-standard=axi \
  --integrated-main-ram-size=0x100000 \
  --qemu-no-run \
  --no-compile
```

The v1 QEMU MMIO protocol still issues each QEMU access as a blocking
single-beat transaction; LiteX converts it when the SoC bus is AXI-Lite or
Wishbone.

## Expected QEMU Machine

The LiteX launcher starts QEMU with:

```sh
qemu-system-riscv32 \
  -M litex-sim,xlen=32,bridge-host=127.0.0.1,bridge-port=1235,\
bridge-base=0x80000000,bridge-size=0x80000000,irq-poll-us=1000,\
reset-addr=0x0,rom-base=0x0,sram-base=0x10000000,main-ram-base=0x40000000,\
clint-base=0xf0010000,clint-size=0x10000,plic-base=0xf0c00000,plic-size=0x400000,\
timebase-freq=1000000,\
csr-base=0xf0000000,csr-size=0x10000 \
  -m 67108864B \
  -nographic -serial none -monitor none \
  -bios build/sim/software/bios/bios.bin
```

For RV64, `qemu-system-riscv64` is used and `xlen=64` is passed.

The QEMU `litex-sim` machine should:

- Instantiate a RISC-V CPU matching `xlen`.
- Own executable ROM/RAM locally inside QEMU.
- Own the RISC-V ACLINT/CLINT and PLIC windows locally inside QEMU.
- Map the LiteX CPU IO window as a low-priority QEMU `MemoryRegion`.
- Forward each MMIO read/write to the LiteX bridge protocol described below.
- Treat non-zero bridge status as a bus error.
- Update QEMU PLIC inputs from the `irq` field returned with each response.
- Poll the bridge with `op=2` when `irq-poll-us` is non-zero, so LiteX-originated
  interrupts can wake QEMU even when the CPU is not otherwise touching MMIO.
- Reset the QEMU CPU when an IRQ poll reports a latched LiteX CPU reset.

## Protocol

All multi-byte fields are little-endian. QEMU opens one TCP connection to
`bridge-host:bridge-port` and performs one blocking request at a time.

Request, 32 bytes:

| Offset | Field   | Size | Value |
|--------|---------|------|-------|
| 0      | magic   | 4    | `0x3051584c` (`LXQ0`) |
| 4      | version | 2    | `1` |
| 6      | op      | 2    | `0` read, `1` write, `2` IRQ poll |
| 8      | size    | 4    | `1`, `2`, `4`, or `8`; `0` for IRQ poll |
| 12     | reserved| 4    | `0` |
| 16     | addr    | 8    | byte address |
| 24     | data    | 8    | write data, little-endian |

Response, 32 bytes:

| Offset | Field   | Size | Value |
|--------|---------|------|-------|
| 0      | magic   | 4    | `0x3052584c` (`LXR0`) |
| 4      | version | 2    | `1` |
| 6      | status  | 2    | `0` ok, `1` Wishbone error, `2` bad request |
| 8      | irq     | 4    | current LiteX interrupt bitmask |
| 12     | reserved| 4    | `0` |
| 16     | data    | 8    | read data, or reset status for IRQ poll |
| 24     | reserved| 8    | `0` |

For an IRQ poll request, QEMU sends `op=2`, `size=0`, `addr=0`, and `data=0`.
The LiteX simulation module replies immediately without issuing a bus
transaction. The response `irq` mask carries the current LiteX interrupt pins,
and response `data[0]` reports a latched LiteX CPU reset request.
