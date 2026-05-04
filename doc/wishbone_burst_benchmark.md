# Wishbone Burst Benchmark Notes

These notes capture the first comparison between LiteX/LiteDRAM before the
Wishbone burst-support work and the current burst-support branch.

## Revisions

Pre-burst baseline:

- LiteX: `97f23539f` (`bios: Harden boot JSON parsing`)
- LiteDRAM: `ef9f94a` (`Merge pull request #379 from trabucayre/IS42VM32160G`)

Current burst branch:

- LiteX: `985225ccc` (`soc: expose L2 cache width tuning`)
- LiteDRAM: `ea756f9` (`test: cover Wishbone burst prefetch backpressure`)

## litex_sim

Command shape:

```sh
PYTHONPATH=<litex>:<litedram> \
python3 -m litex.tools.litex_sim \
    --with-sdram \
    --sdram-data-width=32 \
    --bus-bursting \
    --cpu-type=vexriscv \
    --cpu-variant=full \
    --non-interactive \
    --threads=1
```

Manual BIOS command used after boot:

```sh
mem_speed 0x40000000 8192 1 0
```

The same workload can now be run automatically from `litex_sim`:

```sh
python3 -m litex.tools.litex_sim \
    --with-sdram \
    --sdram-data-width=32 \
    --bus-bursting \
    --wishbone-burst-benchmark \
    --wishbone-burst-benchmark-size=8192 \
    --cpu-type=vexriscv \
    --cpu-variant=full \
    --output-dir=build/sim_burst_benchmark_auto \
    --threads=1
```

This enables the Wishbone burst monitors, runs the BIOS benchmark after SDRAM
initialization, freezes the monitor counters, prints parseable
`wishbone_burst_monitor ... key=value` lines, and exits through the simulation
finish CSR.

Results:

| Revision | Sequential write | Sequential read |
| --- | ---: | ---: |
| Pre-burst | 1.6MiB/s | 491.9KiB/s |
| Current burst | 1.6MiB/s | 535.5KiB/s |
| Current burst, automated 64KiB read-only | - | 542.3KiB/s |

The measured sequential-read gain is about 8.9% for this VexRiscv Full,
32-bit SDRAM, 8KiB L2 configuration.

On the current burst branch, the `litex_sim` Wishbone burst monitor confirmed
actual burst traffic:

| Monitor | Bursts | Burst beats | Max burst beats |
| --- | ---: | ---: | ---: |
| CPU/main_ram side | 3 | 24 | 8 |
| L2/DRAM side | 512 | 1024 | 2 |

The automated 64KiB run still showed a maximum two-beat burst at the L2/DRAM
side while the CPU/main RAM side reached eight-beat bursts.

The L2/DRAM-side two-beat maximum comes from the L2 refill/prefetch shape in
this configuration: the default L2 line is 128 bits, so two 128-bit L2 beats
cover eight 32-bit CPU beats. Sweeping the L2 minimum data width with the
automated benchmark shows that wider L2 lines improve this sequential-read
case:

```sh
python3 -m litex.tools.litex_sim \
    --with-sdram \
    --sdram-data-width=32 \
    --bus-bursting \
    --l2-cache-min-data-width=256 \
    --wishbone-burst-benchmark \
    --wishbone-burst-benchmark-size=65536 \
    --cpu-type=vexriscv \
    --cpu-variant=full \
    --output-dir=build/sim_burst_benchmark_l2w256 \
    --threads=1
```

| L2 minimum data width | Sequential read | L2/DRAM max burst beats |
| ---: | ---: | ---: |
| 64-bit | 428.9KiB/s | 2 |
| 128-bit | 542.3KiB/s | 2 |
| 256-bit | 625.9KiB/s | 2 |
| 512-bit | 676.5KiB/s | 2 |

The 512-bit result is about 37.5% faster than the pre-burst 491.9KiB/s
baseline and about 24.7% faster than the current default 128-bit L2 result.
The Arty A7-35 FPGA sweep below shows the associated resource cost.

## Digilent Arty A7-35 Vivado Build

Command shape:

```sh
PYTHONPATH=<litex>:<litedram>:/home/florent/dev/litex/litex-boards \
python3 /home/florent/dev/litex/litex-boards/litex_boards/targets/digilent_arty.py \
    --build \
    --variant=a7-35 \
    --sys-clk-freq=100e6 \
    --cpu-type=vexriscv \
    --cpu-variant=full \
    --bus-bursting \
    --vivado-max-threads=4
```

Results from place-and-route reports:

| Metric | Pre-burst | Current burst | Delta |
| --- | ---: | ---: | ---: |
| WNS | 0.356ns | 0.795ns | +0.439ns |
| TNS | 0.000ns | 0.000ns | unchanged |
| WHS | 0.036ns | 0.034ns | -0.002ns |
| Slice LUTs | 4592 | 4834 | +242 (+5.3%) |
| LUT as Logic | 4450 | 4692 | +242 (+5.4%) |
| LUT as Memory | 142 | 142 | unchanged |
| Slice Registers | 3737 | 3905 | +168 (+4.5%) |
| Block RAM Tile | 23.5 | 23.5 | unchanged |
| RAMB36 | 11 | 11 | unchanged |
| RAMB18 | 25 | 25 | unchanged |
| DSPs | 4 | 4 | unchanged |
| Combinational loops | 0 | 0 | unchanged |
| Bitstream generation | OK | OK | unchanged |

L2 minimum data-width sweep on the current burst branch:

| L2 minimum data width | Sim 64KiB sequential read | WNS | Slice LUTs | Slice Registers | Block RAM Tile | DSPs | Bitstream |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 128-bit | 542.3KiB/s | 0.795ns | 4834 | 3905 | 23.5 | 4 | OK |
| 256-bit | 625.9KiB/s | 0.568ns | 5072 | 4316 | 31.5 | 4 | OK |
| 512-bit | 676.5KiB/s | 0.712ns | 5606 | 4830 | 47.5 | 4 | OK |

Compared to the current 128-bit default, the 256-bit option gives +15.4%
sequential-read throughput in `litex_sim` for +238 LUTs, +411 registers, and
+8 BRAM tiles on Arty A7-35. The 512-bit option gives +24.7% throughput for
+772 LUTs, +925 registers, and +24 BRAM tiles. The 512-bit option uses 95% of
the A7-35 BRAM tiles, so 256-bit is the more realistic candidate for a small
Artix-7 default or board-level option.

Report paths from the measured builds:

- Pre-burst:
  `/tmp/litex-pre-burst/build/arty_pre_burst/gateware/digilent_arty_timing.rpt`
- Pre-burst:
  `/tmp/litex-pre-burst/build/arty_pre_burst/gateware/digilent_arty_utilization_place.rpt`
- Current burst:
  `build/arty_burst_fixed/gateware/digilent_arty_timing.rpt`
- Current burst:
  `build/arty_burst_fixed/gateware/digilent_arty_utilization_place.rpt`
- Current burst, L2 256-bit:
  `build/arty_burst_l2w256/gateware/digilent_arty_timing.rpt`
- Current burst, L2 256-bit:
  `build/arty_burst_l2w256/gateware/digilent_arty_utilization_place.rpt`
- Current burst, L2 512-bit:
  `build/arty_burst_l2w512/gateware/digilent_arty_timing.rpt`
- Current burst, L2 512-bit:
  `build/arty_burst_l2w512/gateware/digilent_arty_utilization_place.rpt`

## Current Interpretation

The current branch improves this CPU-visible sequential-read case by about 9%
with a modest logic cost and no BRAM or DSP increase on Arty A7-35. Timing is
clean and, for this run, improved versus the pre-burst build despite the extra
logic.

The current maximum observed L2/DRAM-side burst length is two wide L2 Wishbone
beats. For the default 128-bit L2 line this already covers eight 32-bit CPU
beats; increasing the L2 width improves this sequential case but spends BRAM.

## Next Steps

- Repeat the benchmark with larger `mem_speed` ranges to reduce measurement
  noise and expose steady-state behavior beyond the 8KiB L2 size.
- Evaluate `--l2-cache-min-data-width=256` on larger Artix-7/Kintex-7 and
  DDR3/DDR4 targets to see whether the sim throughput gain generalizes without
  excessive BRAM pressure.
- Inspect whether wider L2 lines hurt mixed/random workloads; sequential reads
  benefit, but overfetch can be bad for less linear access patterns.
- Compare CPU variants with different cache line sizes or burst capabilities to
  separate CPU-side limitations from interconnect and LiteDRAM frontend limits.
- Add more non-sim FPGA target reports to check whether the Arty timing and
  BRAM tradeoffs are representative or board-specific.
