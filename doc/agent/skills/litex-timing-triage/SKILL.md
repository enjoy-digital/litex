---
name: litex-timing-triage
description: Triage a LiteX build that fails timing or fails in the toolchain: read the parsed reports (WNS/TNS, per-clock results, failing paths, utilization, errors), classify the failing paths (logic depth, clock crossing, I/O, congestion) and pick the fix in the Python design. Use after a Vivado, Quartus, Gowin, Efinity or nextpnr build of a LiteX design reports negative slack or errors, or when a design works at a lower clock only.
---

# Triage a timing failure

Read the result as data, find which clock and which paths fail, and fix the cause in the
design; tool directives come last.

## 1. Get the report

```sh
python3 -c "import json; from litex.build.report import parse_build_reports; print(json.dumps(parse_build_reports('build/<board>', max_paths=10), indent=1))"
```

With `litex_mcp`: `litex_build_report(job)` or `litex_build_report(output_dir="build/<board>")`.
Parsed reports: Vivado (`gateware/<name>_timing.rpt`, `<name>_utilization_place.rpt`), Quartus
(`.sta.summary`, `.fit.summary`), Gowin (`impl/pnr/`), Efinity (`outflow/`), nextpnr (the Fmax
lines of `litex.log`). The raw report stays the reference for anything the summary lacks:

```sh
grep -n -E "WNS|WHS|VIOLATED" build/<board>/gateware/*timing*.rpt
```

## 2. Classify

| Failing paths look like | Likely cause | Fix in the design |
| --- | --- | --- |
| Many logic levels inside one domain | Deep combinatorial logic | Pipeline (register stages, `stream.PipeValid`/`Buffer`), narrower muxes |
| Source and destination in two clocks | Missing CDC or constraint | `MultiReg`, `PulseSynchronizer`, `stream.ClockDomainCrossing`, false paths |
| From/to a pin | I/O timing | IOB registers, the PHY's delay settings, correct I/O constraints |
| Short logic, long routing, high utilization | Congestion or placement | Smaller design, fewer wide buses, floorplanning last |
| Hold violations | Clock skew or a gated clock | Clocks from the PLL/BUFG, no logic on clocks |

Check first that the failing clock is the one intended: `--sys-clk-freq`, the PLL output and the
period constraints (`platform.add_period_constraint`). A derived or unconstrained clock gives
meaningless slack.

## 3. Separate a marginal implementation from a bug

- Rebuild at a lower `--sys-clk-freq`: if the board then works, the logic is right and timing is
  the issue; if not, it is a logic bug (`litex-csr-debug`, `litescope-capture` skills).
- Compare the slack of a known-good build with the failing one: the new paths show the change
  that broke it.
- Positive timing does not prove the logic correct.

## 4. Tool knobs (last)

- Vivado: `--vivado-synth-directive`, `--vivado-place-directive`, `--vivado-route-directive`,
  `--vivado-post-route-phys-opt-directive`, `--vivado-max-threads`.
- nextpnr: `--nextpnr-seed`, `--nextpnr-timingstrict` (fail the build on a timing failure);
  Yosys: `--yosys-abc9`, `--yosys-nowidelut`.
- Each is a target option where the toolchain supports it (`--help` lists them). A seed that
  passes once is not a fix: say so in the report.

## Pitfalls

- An analyzer (LiteScope) added for debugging adds its own paths: remove it or put it in `sys`.
- Wide CSRs on slow fabrics fail the CSR bus timing: index plus data registers instead.
- False paths hide real crossings: constrain only paths that are synchronized in the design.
- Report what ran: toolchain and version, the clock targets, WNS/TNS before and after.

## See also

- https://github.com/enjoy-digital/litex/wiki/Debug-A-SoC-On-Hardware#read-the-generated-design
- https://github.com/enjoy-digital/litex/wiki/Build-Backends
- https://github.com/enjoy-digital/litex/blob/master/litex/build/report.py
