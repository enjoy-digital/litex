# CPU-cycle benchmarks in LiteX Sim

This bare-metal microbenchmark uses `litex.tools.litex_sim.SimSoC` and its
Verilator backend. It measures **simulated system-clock cycles**, not host
simulation speed. The CPU and bus share the system clock.

Run from a LiteX checkout with the usual LiteX Sim dependencies installed
(including LiteEth, LiteDRAM, Verilator, a RISC-V GCC toolchain and the
VexRiscv/compiler-rt/picolibc pythondata packages):

```sh
python3 -m litex.soc.software.bench.sim --output-dir=/tmp/cpu-baseline
python3 -m litex.soc.software.bench.sim --output-dir=/tmp/cpu-burst --bus-bursting
python3 -m litex.soc.software.bench.sim --output-dir=/tmp/cpu-sdram --with-sdram
```

Use a **new** output directory per run; existing directories are rejected to
avoid stale binaries or results. Each run builds its own
firmware and simulator, checks the results, and saves `benchmark.json` with all
three samples and their medians. `benchmark.log` retains serial output;
`compile.log` retains simulator compilation output. `--timeout` bounds the
simulation, not the build. `--jobs` controls the Verilator build parallelism.
JSON build metadata records the compiler, Verilator, LiteX revision, CPU flags,
clock frequency, firmware hashes and RTL hashes. The revision alone does not
describe uncommitted source edits; compare the hashes as well.

The default is VexRiscv `standard`, a shared 32-bit Wishbone bus, 64 KiB ROM,
32 KiB SRAM and 256 KiB integrated main RAM. `--with-sdram` replaces main RAM
with LiteX Sim's SDR SDRAM model and an 8 KiB L2. Use `--help` for CPU variant,
bus, decoder-register and L2 configuration options. These are experiments:
a wider bus or a larger CPU variant is not necessarily faster.

`--min-l2-data-width` changes the minimum L2 refill width in bits without
changing the CPU bus width. For example, `--with-sdram --min-l2-data-width=256`
tests 32-byte cache lines with this SDR model. The same option is available in
`litex_sim`; it defaults to the existing 128-bit width. Larger lines can help
sequential accesses but fetch unused data on sparse accesses.

## Measurement contract

- Firmware is compiled at `-O2`, executes from ROM and keeps its stack in SRAM.
  The last 64 KiB of main RAM holds the test buffer, separate from L2 eviction
  traffic. Interrupts are disabled; SDRAM initialization is outside measurements.
- A latched 32-bit hardware counter advances once per system-clock cycle.
  This works even when a CPU variant does not expose a readable `mcycle` CSR.
  Fences order timed memory operations. Counts include sampling overhead;
  `overhead_0` measures a back-to-back sample for each configuration. Individual
  measurements must finish within one counter wrap.
- `compute` performs 32,768 dependent integer multiply/add iterations.
- `write`, `read_cold` and `read_repeat` traverse 1 KiB and 64 KiB buffers using
  volatile 32-bit accesses, unrolled eight times. The first read follows cache
  eviction; the repeat immediately follows that read. The larger working set
  need not fit L1, so **repeat does not imply an L1 hit**.
- `chase` performs 8,192 dependent loads through a verified pointer ring with
  one node per 64-byte block. Each run begins after cache eviction and includes
  both initial misses and subsequent revisits.
- Checksums, sample counts, completion and positive cycle counts are mandatory.
  Failed or incomplete runs do not produce a new result file.

These are compute and data-memory microbenchmarks, not CoreMark, an instruction
cache stress test, an OS workload or proof of maximum application performance.
Writes measure CPU-visible completion, not forced L2 writeback to SDRAM.
Simulation does not establish achievable FPGA clock frequency, timing closure,
resource cost or power. LiteX Sim uses a 1 MHz system clock but SDRAM timing
parameters derived at 100 MHz; compare cycles under the same model rather than
interpreting its printed bandwidth as board performance.
