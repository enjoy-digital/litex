# AGENTS.md: LiteX

LiteX builds FPGA SoCs and cores in Python (Migen), with the SoC builder, interconnect, in-tree
cores, CPUs, build backends, BIOS/software and host tools. The cores ecosystem (LiteDRAM, LiteEth,
LitePCIe, LiteScope...) lives in sibling repositories with their own AGENTS.md.

Read the LiteX agent page first: https://github.com/enjoy-digital/litex/wiki/LiteX-for-AI-Agents (framework map, conventions, how to
verify a change, contribute back). Index of the whole wiki for agents: https://github.com/enjoy-digital/litex/wiki/llms.txt.

## Where things are

- `litex/soc/integration/`: `soc.py` (`SoC`, `LiteXSoC`, `SoCCore`, the `add_*` helpers), `builder.py`, `export.py`.
- `litex/soc/cores/`: in-tree cores; `cpu/<name>/core.py` (CPU wrappers); `clock/` (PLLs per vendor).
- `litex/soc/interconnect/`: `stream.py`, `wishbone.py`, `axi/`, `csr*.py`.
- `litex/build/`: platforms and toolchains per vendor, `sim/` (Verilator), `report.py` (parsed timing/utilization).
- `litex/soc/software/`: BIOS, libbase, liblitedram/libliteeth/...; `litex/tools/`: `litex_server`, `litex_cli`, `litex_term`, `litex_sim`, `litex_mcp`.
- `doc/wiki/`: the wiki sources (`python3 doc/wiki_sync.py check --strict`); `test/`: pytest suite.

## Verify a change

```sh
python3 -m pytest test/<area>/test_<thing>.py              # the closest tests first
python3 -m litex_boards.targets.<board> --build --no-compile  # elaborate a target using the code (seconds, no toolchain)
litex_sim --cpu-type=vexriscv                               # BIOS in Verilator for anything the BIOS exercises
```

An import proves nothing; elaboration proves the Python and the Verilog generation; timing and
analog behavior need a real build and a board (say in the PR what ran where).

## Rules

- Style: https://github.com/enjoy-digital/litex/blob/master/doc/coding_style.md (match the
  surrounding file; `module: Description of the change.` commit titles; one change per commit).
- Never edit generated files (`build/`, `csr.h`, `csr.csv`, the Verilog): change the Python.
- One topic per pull request, from `master`, with what was tested and on which hardware; say
  that an agent wrote it and who supervised. Do not rename options or reformat unrelated code.
- Hardware: never flash a board or write its SPI flash unless the user asked; `--load` (volatile)
  is the default for experiments.

## Debug on hardware

Method: https://github.com/enjoy-digital/litex/wiki/Debug-A-SoC-On-Hardware (check the link and `--ident` first, registers before
traces, narrow LiteScope captures). `litex_mcp` gives the same loop as MCP tools (CSRs by name,
LiteScope captures, builds with parsed timing, simulation): https://github.com/enjoy-digital/litex/wiki/LiteX-for-AI-Agents#drive-a-soc-through-mcp.

## Skills

`doc/agent/skills/<name>/SKILL.md` (Agent Skills format): build and load, board bring-up, CSR
debug, LiteScope captures, timing triage, upstreaming a fix. Read the one that matches the task;
in Claude Code, install them with `/plugin marketplace add enjoy-digital/litex` then
`/plugin install litex@litex`.
