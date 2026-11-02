A method more than a tool: how we find out why a LiteX design misbehaves on a board. Observe
through small registers first, capture with LiteScope only once the question is narrow, read
the generated Verilog, and turn every finding into a test. It works the same whether a person
or an agent runs the loop, and it reuses the tools of the previous pages.

## Try it

Check the link and the SoC you are talking to before anything else, here on a simulated SoC
(no board needed):

```sh
litex_sim --uart-name=crossover+uartbone --uart-tcp --uart-tcp-port=2345 --output-dir=build/sim
litex_server --uart --uart-port=socket://localhost:2345 --bind-port=1240
litex_cli --csr-csv=build/sim/csr.csv --port=1240 --ident
litex_cli --csr-csv=build/sim/csr.csv --port=1240 --regs --filter=ctrl
```

```
LiteX Simulation 2026-11-02 15:59:20
0xf0000000 : 0x00000000 ctrl_reset
0xf0000004 : 0x12345678 ctrl_scratch
0xf0000008 : 0x00000000 ctrl_bus_errors
```

The identifier says which SoC answers on the port, `ctrl_scratch` reads back its reset value
(`0x12345678`) and `ctrl_bus_errors` counts the bus accesses that hit nothing. Three numbers, and
the transport, the CSR map and the bus are known to work.

## The loop

1. Reproduce the failure and write down the exact build command, bitstream, transport and host
   command, with what you observe.
2. Find a known-good build and one minimal failing change.
3. Check the host path with a trivial access: `--ident`, `ctrl_scratch`, a project `info` command.
4. Read what the build generated: `csr.csv`/`csr.json`, `csr.h`, `mem.h`, the Verilog.
5. If polling can answer the next question, add a register (a counter, a status).
6. If the question is about timing or a handshake, add a narrow LiteScope probe.
7. Rebuild, load, capture, and record the result.
8. Fix the cause in the smallest layer that has it.
9. Add the test that would have caught it.
10. Commit the fix apart from the exploratory instrumentation (unless the probe is reusable).

The fastest path is often: hardware symptom, generated Verilog, one narrow trace, fix. Broad
instrumentation first mostly costs rebuilds.

## Check the link first

- Run `litex_server` on its own `--bind-port` when another server may be listening, and check
  `--ident` before reading anything: a client on the default port can be talking to another board.
- With several JTAG/USB-UART adapters plugged in, select the board's one explicitly.
- Shifted strings in the identifier, impossible values or reads of 0 everywhere mean a broken
  bridge or a wedged board: fix that before debugging the feature.
- If host writes pile up but nothing happens in the SoC, the transport is fine and the problem is
  on the bus or in a state machine.

## Registers before traces

| Register | Answers |
| --- | --- |
| Counter (events, errors, timeouts) | How often, and does it move when I do X? |
| Sticky flag, cleared by software | Did it ever happen since I last looked? |
| FSM state snapshot | Where is it stuck? |
| History buffer (last N states, timestamps) | How far did it get, and how long each step took? |

- On slow fabrics, prefer an index register plus a data register to wide CSRs: wide ones can
  break the CSR bus timing.
- Counters in a clock domain that gets reset (a recovered clock, a PHY domain) are cleared with
  it: keep bring-up counters reset-less.
- When a register is worth keeping, give it a stable name and host-side access (a script, a
  utility command), so the next person starts from it.
- A gateware master that reaches CSRs through the main bus needs the full address,
  `self.get_csr_address("name")`; `self.csr.address_map(name, origin=True)` is a CSR-local offset.

## LiteScope, narrowly

- Ask one question per capture ("does the master issue a read?", "which state holds?") and
  probe only what answers it: control and FSM bits before data, one bus rather than all.
- Stay below 128 captured bits (256 can work), with one clock domain per analyzer; prefer the
  `sys` domain, an analyzer in a fast transceiver domain can fail timing itself.
- A short depth with a precise trigger beats a deep blind capture; `--subsampling` covers
  millisecond-long sequences on level signals.
- Put the probe groups behind target switches (`--with-xxx-probe`) and wrap the captures in a
  script that re-arms until the trigger fires and decodes the result.
- The end of a failure can mislead: when the final state does not explain it, trigger at the
  start of the sequence.

## Read the generated design

Inspect the Verilog when the symptom involves an address, a size, a decoder boundary, a bus
width, a reset or a clock domain:

```sh
grep -n "module_or_signal" build/<board>/gateware/<board>.v
grep -n -E "WNS|WHS|VIOLATED" build/<board>/gateware/*timing*.rpt
```

- Bus checks: byte- versus word-addressed Wishbone, `adr[31:2]` dropped by an adapter, decoder
  masks when a region size crosses a power of two, local offsets used as full addresses.
- Timing versus logic: compare the failing and working builds' slack, rebuild at a lower
  `--sys-clk-freq`, look at clock crossings and reset release. Positive timing does not prove
  the logic correct; timing experiments only separate a marginal implementation from a
  deterministic bug.
- The vendor tools can be the bug: synthesizing the design alone and simulating the netlist
  settles it.

## Test from the inside out

For a data path, test the layers before the outside world: a loopback in the FPGA, then through
the PHY, then through the external chip, each with a pass/fail result and counters that split
the failure classes (drops on the host side, wrong source, ring full, recovered timeouts). Check
the state a program leaves behind (a stream still selected, a loopback still enabled): the next
program would inherit it.

## Close the loop

- Put the regression test in the layer that failed; a LiteX framework bug gets its test in
  LiteX, not only in the project.
- Even for a bug found on hardware, capture an invariant in software: an address computation,
  a CSR map, a generated constant, a parser.
- The commit or debug note says: the build command, the transport, the timing summary, the host
  commands, the register values or LiteScope signals that prove the conclusion, the tests run.
- Keep reusable probes, scripts and tests in the tree. A `doc/debugging-guide.md` per project,
  kept current, saves the next person (or agent) the rediscovery.

## Next

- [Control it from the host](Host-Bridges.md): the bridges and tools every step above relies on.
- [Look inside with LiteScope](Use-LiteScope-To-Debug-A-SoC.md): setting up the analyzer used in the narrow captures.
- [Debug the CPU with GDB](Debug-With-GDB.md): when the hardware is fine and the bug is in the code.
- [LiteX for AI agents](LiteX-for-AI-Agents.md#drive-a-soc-through-mcp): the same loop driven by an agent through `litex_mcp`.
