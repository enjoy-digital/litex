# LiteX Test Layout

Tests are grouped by the subsystem under test, not by whether they use
`unittest` or pytest-native functions.

- `interconnect/`: buses, streams, packets, DMA and CSR interconnect logic.
- `cores/`: hardware cores and protocol blocks such as UART, SPI, video, RAM,
  clocking, GPIO, JTAG and related helpers.
- `build/`: platform, backend, vendor toolchain and simulation build helpers.
- `hdl/`: HDL generation, converters, Migen/LiteX compatibility and small
  language-level helpers.
- `soc/`: SoC integration, builder/export behavior, CPU policy checks and
  full-system generation tests.
- `software/`: BIOS, demo and host-side software coverage.
- `tools/`: LiteX command-line tools and remote/client utilities.
- `support/`: shared helpers used by multiple test modules.

When adding coverage, prefer the narrowest matching directory. Only add helpers
to `support/` after they are shared by at least two test modules.
