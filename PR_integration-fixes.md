# soc/integration: Fix bugs/robustness issues and improve usability (review fixes)

This PR is the result of a systematic review of `litex/soc/integration/` (soc.py, builder.py, export.py, common.py, doc.py) for bugs, robustness issues and usability problems, following the same approach as the BIOS review (#bios-fixes). 12 commits, one fix per commit.

## Bugs

- **Region decoding on byte-addressed Wishbone buses was broken**: `SoCRegion.decoder()` always converted origins to word units, but `wishbone.Decoder` passes raw byte addresses with `--bus-addressing byte` - every non-zero-origin region was undecodable (accesses select no slave and time out). Confirmed and verified by simulation.
- **Plain `SoC`/`LiteXSoC.finalize()` crashed**: `self.config` was only initialized in `SoCCore.__init__` (fallout of the SoCCore-move refactor); a CSR interconnect with zero banks also died with a cryptic migen `TypeError`, and SoC-level CSRs silently clobbered a user module named `main`.
- **Region validation holes**: regions extending beyond the bus address space were accepted silently (producing dead slaves); IO regions added after cached regions (the normal CPU flow: reserved regions exist before `add_cpu` adds the IO regions) skipped overlap re-checking; `add_slave` accepted an `SoCIORegion` and crashed with a bare `KeyError` at finalize; misaligned slave regions now error early *with the slave's name*.
- **Duplicate guards checking the wrong names**: `add_etherbone` checked `{name}_ethcore` but registers `ethcore_{name}`; `add_spi_ram` checked names it never registers; `add_ram` registered the bus slave before its name check.
- **`add_uart` uartbone handling**: `uart_name="uartbone"` dropped `with_dynamic_baudrate` and allocated an IRQ slot + `UART_INTERRUPT` constant for a UART that does not exist.
- **Generated-code correctness (export.py)**: soc.h emitted ill-formed C for >32-bit constants (unsuffixed decimal literals; >64-bit values silently broken) and for strings containing control characters (`\uXXXX` UCNs); csr.json re-exported imported read-only CSRs as `rw`, contradicting csr.h; the fields-only csr.h variant referenced undefined `_read`/`_write` functions (now verified by compiling the generated header with gcc).
- Leftover debug `print()` removed from `LiteXModule.__iadd__` (spammed stdout on every `m += module`).

## Robustness / usability

- SoCCore warns on unknown keyword arguments (typos were silently swallowed by `**kwargs`; `l2_size` stays tolerated for the argdict passthrough - `litex_sim` runs warning-free).
- `add_sdram`/`add_video_*` validate their phy/module arguments like their siblings; `add_video_framebuffer` gets its missing duplicate checks; `add_adapter` raises named `SoCError`s for unsupported conversions; `init_rom` with empty contents no longer creates a depth-0 Memory.
- Builder: export paths get their parent directories created; paths Make cannot represent (spaces/`#`) fail loudly instead of corrupting variables.mak (`$` now escaped); imported JSONs parsed once instead of three times and merged only once (second `build()` no longer raises spurious collisions); `--soc-csv`/`--soc-json` help documents that they are always generated.
- SVD `]]>` CDATA escaping; `add_pcie` warns on ignored `msis` and name-prefixes its DMA constants (legacy unprefixed kept for the default instance); `--uart-with-dynamic-baudrate`/`--uart-rx-fifo-rx-we` exposed on the parser; `--jtagbone-chain` accepts hex; `SoCRegion` raises `SoCError` consistently instead of `ValueError`.

## Verification

- `pytest`: test_soc/test_builder/test_export/test_integration - all tests with available toolchains/dependencies pass (the `test_cpu` failures on this machine are pre-existing environment gaps: missing lm32/or1k/ppc toolchains, pythondata packages, Amaranth, GHDL - verified identical before/after).
- `litex_sim` builds pass (featured ethernet+sdcard+spiflash, and serv); **generated csr.h/soc.h/mem.h are byte-identical to master's output** (the header diff was used as a regression gate during the work).
- End-to-end Verilator run: BIOS boots to the `litex>` prompt.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
