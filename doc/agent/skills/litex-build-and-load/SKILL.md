---
name: litex-build-and-load
description: Build a LiteX SoC (a LiteX-Boards target or a target script), check what it generates, read the build result and load the bitstream on the board. Use when asked to build, elaborate, compile, load or flash a LiteX design, or to find the command line for a board, a CPU and a set of cores.
---

# Build and load a LiteX SoC

A LiteX design is a *platform* (the board) and a *target* (the SoC). Every target takes
`--build`, `--load` and the SoC/Builder/toolchain options; `--help` lists them with defaults.

## 1. Find the command line

```sh
python3 -m litex_boards.targets.<board> --help        # every option of the target, by group
python3 target.py --help                               # same for a target script
```

With `litex_mcp`: `litex_list_boards(filter)`, `litex_board_info(name, sections=["Target", "SoC"])`
(FPGA device, platform class, the options of each group), `litex_list_cpus(filter)` (with their
variants), `litex_list_cores()` (which ecosystem cores are installed).

## 2. Elaborate first (seconds, no toolchain)

```sh
python3 -m litex_boards.targets.<board> [options] --build --no-compile --output-dir=build/<board>
```

Read `build/<board>/csr.csv` (or `csr.json`) for the memory map, CSRs, IRQs and constants, and the
Verilog in `build/<board>/gateware/`. `--no-compile-gateware` also builds the BIOS and the headers
(needs the CPU's gcc, meson and ninja).

## 3. Build

```sh
python3 -m litex_boards.targets.<board> [options] --build --output-dir=build/<board>
```

With `litex_mcp`: `litex_build_start(target, args, output_dir)` (board name or `.py` script, runs
`--build` as a background job), `litex_job_wait(job, timeout=600)` (repeat: one call waits at
most 600 s), then `litex_build_report(job)`: timing met or not, WNS/TNS, per-clock results,
failing paths, utilization, error lines. Without MCP, the same data:

```sh
python3 -c "import json; from litex.build.report import parse_build_reports; print(json.dumps(parse_build_reports('build/<board>'), indent=1))"
```

Timing not met: use the `litex-timing-triage` skill before loading anything.

## 4. Load

```sh
python3 -m litex_boards.targets.<board> [same options] --load --output-dir=build/<board>
litex_term /dev/ttyUSBx                                # the BIOS console (--speed for another baudrate)
```

`--load` is volatile (SRAM configuration), `--flash` (on the targets that have it) writes the
SPI flash. Through `litex_mcp`, both are refused unless the server runs with `--allow-write`.

## Pitfalls

- Never `--flash` unless the user asked: `--load` is the default for experiments.
- Pass the same options to `--load` as to `--build` (at least `--output-dir`): the target looks
  for the bitstream in its gateware directory, under the build name.
- The Builder writes `build/<platform>/` by default: give `--output-dir` when several variants are
  built, and pass the matching `--csr-csv` to the host tools.
- `litex_build_start` writes in a temporary job directory unless `output_dir` is given; files a
  target writes in the current directory (such as `analyzer.csv`) land in the MCP server's
  directory.
- Option names use dashes; sizes and baudrates are integers (`--uart-baudrate=1000000`); CPU
  variants are exact keys (`litex_list_cpus`).
- Toolchains are found through the `PATH` (or `LITEX_ENV_VIVADO`/`LITEX_ENV_ISE`/`LITEX_ENV_EFINITY`);
  `--toolchain` selects another one when the platform supports it.
- An import proves nothing; elaboration proves the Python and the Verilog; only a real build
  proves timing.

## See also

- https://github.com/enjoy-digital/litex/wiki/SoC-builder
- https://github.com/enjoy-digital/litex/wiki/Load-And-Flash
- https://github.com/enjoy-digital/litex/wiki/LiteX-for-AI-Agents#drive-a-soc-through-mcp
