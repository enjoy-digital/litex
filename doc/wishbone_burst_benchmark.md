# Wishbone Burst Benchmark Notes

These notes capture the first comparison between LiteX/LiteDRAM before the
Wishbone burst-support work and the current burst-support branch.

## Revisions

Pre-burst baseline:

- LiteX: `97f23539f` (`bios: Harden boot JSON parsing`)
- LiteDRAM: `ef9f94a` (`Merge pull request #379 from trabucayre/IS42VM32160G`)

Current burst branch:

- LiteX: `c7578d364` (`interconnect: reuse tag port for cache prefetch lookup`)
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

Results:

| Revision | Sequential write | Sequential read |
| --- | ---: | ---: |
| Pre-burst | 1.6MiB/s | 491.9KiB/s |
| Current burst | 1.6MiB/s | 535.5KiB/s |

The measured sequential-read gain is about 8.9% for this VexRiscv Full,
32-bit SDRAM, 8KiB L2 configuration.

On the current burst branch, the `litex_sim` Wishbone burst monitor confirmed
actual burst traffic:

| Monitor | Bursts | Burst beats | Max burst beats |
| --- | ---: | ---: | ---: |
| CPU/main_ram side | 3 | 24 | 8 |
| L2/DRAM side | 512 | 1024 | 2 |

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

Report paths from the measured builds:

- Pre-burst:
  `/tmp/litex-pre-burst/build/arty_pre_burst/gateware/digilent_arty_timing.rpt`
- Pre-burst:
  `/tmp/litex-pre-burst/build/arty_pre_burst/gateware/digilent_arty_utilization_place.rpt`
- Current burst:
  `build/arty_burst_fixed/gateware/digilent_arty_timing.rpt`
- Current burst:
  `build/arty_burst_fixed/gateware/digilent_arty_utilization_place.rpt`

## Current Interpretation

The current branch improves this CPU-visible sequential-read case by about 9%
with a modest logic cost and no BRAM or DSP increase on Arty A7-35. Timing is
clean and, for this run, improved versus the pre-burst build despite the extra
logic.

The current maximum observed L2/DRAM-side burst length is two 32-bit Wishbone
beats. Further throughput work should focus on why wider CPU cache refills are
still fragmented before reaching LiteDRAM.

## Next Steps

- Repeat the benchmark with larger `mem_speed` ranges to reduce measurement
  noise and expose steady-state behavior beyond the 8KiB L2 size.
- Add an automated sim benchmark mode that clears burst monitors, runs a fixed
  memory workload, dumps counters, and exits without console interaction.
- Inspect the L2 cache refill path and LiteDRAM Wishbone frontend to understand
  the current two-beat limit on the L2/DRAM side.
- Compare CPU variants with different cache line sizes or burst capabilities to
  separate CPU-side limitations from interconnect and LiteDRAM frontend limits.
- Add at least one non-sim FPGA target report to check whether the Arty timing
  result is representative or just placement variance.
