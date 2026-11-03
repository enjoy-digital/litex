# Timing triage of a Vivado build

`vivado_build/` contains the output of a Vivado build of a LiteX SoC (CPU, DRAM, Ethernet) on an
Artix-7: the toolchain reports are in `vivado_build/gateware/`. The bitstream was generated but the
Ethernet receive path of the board drops frames.

Triage the timing of this build from the reports and write your answer to `answer.json` in this
directory, with this format:

```json
{
  "timing_met"     : false,
  "wns_ns"         : -1.234,
  "tns_ns"         : -5.678,
  "failing_clocks" : ["clk_a", "clk_b"],
  "worst_paths"    : [
    {"clock": "clk_a", "slack_ns": -1.234, "source": "a_reg[0]/C", "destination": "b_reg[3]/D"}
  ]
}
```

- `timing_met`: whether all the timing constraints are met.
- `wns_ns`, `tns_ns`: worst and total negative setup slack of the design, in ns.
- `failing_clocks`: every clock with a setup violation.
- `worst_paths`: the 3 worst failing setup paths, worst first.

Do not modify the reports. No toolchain run is needed (or available).
