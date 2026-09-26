# LiteX Core Flow and HarmonyOS Porting Points

## Scope

The first porting phase covers the LiteX Python core and export-only SoC
generation. It does not require FPGA vendor synthesis, place-and-route,
bitstream loading, Verilator execution, or CPU firmware compilation.

## Core Flow

```text
Migen modules and signals
        |
        v
LiteX cores, buses, CSRs, and SoC integration
        |
        v
SoC.finalize()
        |
        +--> CSR and memory maps
        +--> constants and software headers
        +--> module hierarchy and clock domains
        |
        v
Builder
        |
        +--> csr.csv / csr.json
        +--> software/include/generated/*.h
        +--> gateware/<build-name>.v
        |
        v
Optional external stages
        +--> CPU cross compiler and BIOS
        +--> Verilator simulation
        +--> vendor synthesis and bitstream tools
```

The `examples/minimal_soc_baseline.py` example stops after the Builder export
stage. Its small export-only toolchain emits Verilog without invoking an
external executable.

## Main Ownership Boundaries

| Layer | Main paths | Porting concern |
|---|---|---|
| Migen integration | `migen.*`, `litex/gen/` | Python bytecode/reflection behavior and automatic names |
| Platform abstraction | `litex/build/generic_platform.py`, `litex/build/*/` | path handling, executable discovery, constraints, temporary files |
| SoC integration | `litex/soc/integration/soc.py` | bus/CSR finalization, clock domains, CPU configuration |
| Builder/export | `litex/soc/integration/builder.py`, `export.py` | generated paths, text encoding, headers, JSON/CSV determinism |
| Command-line tools | `litex/tools/` | argument parsing, subprocesses, sockets, serial ports |
| Simulation | `litex/build/sim/`, `litex/tools/litex_sim.py` | C/C++ compiler, Verilator, libraries, process lifecycle |
| CPU/software | `litex/soc/cores/cpu/`, `litex/soc/software/` | Python data packages, Meson, Ninja, cross GCC |

## HarmonyOS Compatibility Checkpoints

### Python runtime

- Confirm native CPython version and architecture.
- Verify `venv`, `pip`, editable installs, UTF-8 file I/O, and package entry
  points.
- Record Migen automatic-name failures separately from OS-specific failures.

### File system and paths

- Use `pathlib`/`os.path` instead of hard-coded separators.
- Check absolute paths, temporary directories, executable suffixes, and case
  sensitivity.
- Compare generated files after normalizing timestamps and absolute paths.

### Processes and tools

- Check `subprocess` command construction and executable lookup.
- Distinguish a missing external tool from a LiteX Python failure.
- Keep Verilator, cross GCC, and vendor tools outside core acceptance until
  native availability is confirmed.

### Serial and networking

- Verify PySerial import before testing device enumeration.
- Treat serial naming, raw-device access, TAP interfaces, and socket behavior as
  optional platform integrations, not core import blockers.

### Encoding and permissions

- Record the locale and default encoding.
- Open generated text with explicit UTF-8 where possible.
- Check temporary-file deletion and file-locking behavior.

## Required First-Phase Outputs

The Windows and HarmonyOS runs must both produce:

- an environment report;
- successful LiteX/Migen imports;
- results for the 24 portable core tests;
- `minimal_soc.v`;
- `csr.csv` and `csr.json`;
- generated software headers;
- a machine-readable acceptance report.

Only after these outputs agree should the project advance to firmware
compilation, Verilator, or physical FPGA validation.
