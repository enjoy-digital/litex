---
name: litescope-capture
description: Capture internal signals of a running LiteX SoC with the LiteScope logic analyzer (add a narrow probe to the target, rebuild, trigger, read the capture as data or VCD) through litescope_cli --json or the litex_mcp scope tools. Use when a question about timing, a handshake or a state sequence cannot be answered by polling registers.
---

# Capture signals with LiteScope

One question per capture, the fewest signals that answer it, a precise trigger. Registers first
(`litex-csr-debug` skill): a probe costs a rebuild.

## 1. Add the analyzer to the target

```python
from litescope import LiteScopeAnalyzer

analyzer_signals = [fsm_state, bus.valid, bus.ready, bus.first, bus.last, error]  # control before data
self.analyzer = LiteScopeAnalyzer(analyzer_signals,
    depth        = 512,
    clock_domain = "sys",
    samplerate   = sys_clk_freq,
    csr_csv      = "analyzer.csv")
```

Put it behind a target switch (`--with-<feature>-probe`) so the default build stays clean. The SoC
needs a host bridge (`--with-uartbone`, `--uart-name=crossover+uartbone`, `--with-jtagbone`,
`--with-etherbone`). `litex_sim --with-analyzer` has one built in to try the flow without a board.

## 2. Capture

```sh
litex_server --uart --uart-port=/dev/ttyUSBx --bind-port=1240
litescope_cli --csr-csv=build/<board>/csr.csv --csv=analyzer.csv --port=1240 --list --json
litescope_cli --csr-csv=build/<board>/csr.csv --csv=analyzer.csv --port=1240 \
    -r <signal> --offset=32 --length=256 --timeout=10 --json --dump=capture.vcd
```

Triggers: `-r`/`--rising-edge`, `-f`/`--falling-edge`, `-v <signal> <value>` (`--value-trigger`);
none means an immediate capture. `--group` selects a group, `--subsampling=N` keeps one sample in
N (long sequences on level signals). With `--json` the result is one object with
`"triggered"`; exit code 2 when the trigger did not fire within `--timeout`, 1 on errors.

With `litex_mcp`: `litex_scope_list(analyzer_csv)`, then
`litex_scope_capture(analyzer_csv, group, triggers=[{"signal": "...", "type": "rising"}], offset, length, timeout, signals)`
(types `rising`, `falling`, `value` with `"value": "0x10"`). It returns, per signal, the value at
the trigger, the transition count and the first changes, plus the path of a VCD of the whole
capture: read the summary first, open the VCD only when needed.

## 3. Read and decide

- The trigger sits at sample `offset`; look at what changes around it, not at the end of the
  buffer.
- The final state does not explain the failure: trigger at the start of the sequence instead.
- Did not trigger: the condition never happened, or the signal is in another clock domain than
  the analyzer, or the trigger signal is not in the selected group.

## Pitfalls

- Stay below about 128 captured bits (256 can work); depth x width uses block RAM.
- One clock domain per analyzer; prefer `sys`. An analyzer in a fast transceiver domain can fail
  timing itself.
- `analyzer.csv` is written in the directory the build ran from (or the path given to `csr_csv=`),
  not next to `csr.csv`; a stale one decodes the wrong layout. Its file name sets the CSR prefix
  the client looks for (`analyzer.csv` -> `analyzer_*`).
- A capture without `--timeout` waits forever for its trigger.
- Keep reusable probes in the tree (behind their switch); remove the exploratory ones before
  committing the fix.

## See also

- https://github.com/enjoy-digital/litex/wiki/Use-LiteScope-To-Debug-A-SoC
- https://github.com/enjoy-digital/litex/wiki/Debug-A-SoC-On-Hardware#litescope-narrowly
- https://github.com/enjoy-digital/litescope/blob/master/AGENTS.md
