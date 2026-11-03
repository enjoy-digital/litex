# LiteX Agent Evaluation

Small debug tasks to measure whether an AI coding agent debugs LiteX SoCs better with the LiteX
MCP server (`litex/tools/litex_mcp.py`) than with the shell tools only (`litex_server`,
`litex_cli --json`, `litescope_cli`, `litex_term`). Each task is a realistic symptom on a small
simulated SoC (Verilator, no hardware, no `sudo`), on saved toolchain reports or (optional) on an
ECPIX-5 board, with an automatic checker.

## Tiers

- **v1, fault visible in the source**: the bug is in the target the agent is given; reading it is
  enough (and is what agents do first). Measures source reading more than live debugging.
- **v2, fault only visible at runtime**: the faulty part cannot be read cheaply (synthesized
  netlist, prebuilt firmware, data-dependent behavior, generated artifact): observing the running
  SoC (CSRs, memory, console, LiteScope) is the efficient path. The checkers run the delivered
  parts (reference SoC/netlist/firmware), so rewriting them does not pass.

| Task            | Tier | Symptom given to the agent                          | Needs            | Checker                                       |
|-----------------|------|-----------------------------------------------------|------------------|-----------------------------------------------|
| `csr_address`   | v1   | A host script prints a wrong sensor temperature.    | Sim, CSRs        | Reference SoC with another reading, runs the script. |
| `ticker_reset`  | v1   | A ticker delay never expires.                       | Sim, CSRs        | Builds the agent's SoC, checks the peripheral against its spec. |
| `fsm_stuck`     | v1   | A checksum engine never completes.                  | Sim, LiteScope   | Builds the agent's SoC, runs the engine on 5 lengths/seeds. |
| `bios_memtest`  | v1   | The BIOS reports a memory initialization failure.   | Sim, CPU/console | Builds the agent's SoC, checks the boot log and the main RAM. |
| `timing_triage` | v1   | Timing triage of a Vivado build (offline).          | Reports          | Compares `answer.json` with the reports.      |
| `opaque_gain`   | v2   | A vendor IP (netlist + datasheet) returns wrong results. | Sim, bus/memory | Reference SoC and netlist, agent's `driver.configure()`, then drives the IP itself. |
| `stream_packer` | v2   | A packer test loses some packets under back-pressure. | Sim, CSRs, LiteScope | Reference harness with the agent's `packer.py`, 5 length/back-pressure mixes + throughput. |
| `firmware_blob` | v2   | A prebuilt firmware prints a channel check failure. | Sim, CPU/console, CSRs | Agent's SoC with the delivered binary and other ADC values, parses the console. |
| `stale_regs`    | v2   | A host application prints wrong board information.  | Sim, CSRs        | Reference SoC with other values, runs the agent's application. |
| `ecpix5_scaler` | v2   | The vendor IP on hardware (ECPIX-5) returns wrong results. | ECPIX-5, bus  | Builds/loads (SRAM) the reference SoC, agent's `driver.configure()`, drives the IP. |

v2 faults (do not give these to the agent):

- `opaque_gain`: the netlist (3800 lines of anonymous gates) is rev 1.1, the datasheet rev 1.0:
  GAIN is Q4.12 instead of Q8.8 and the reserved register 0x18 is a LIMIT register resetting to
  4095. Probing the IP (ID, reset values, a known input) finds both; reading the netlist does not.
- `stream_packer`: the packer's skid buffer stores the payload but not `last`: a packet whose last
  word completes while the output is held merges with the next one. Fine without back-pressure;
  the failing case is found with the test counters and a LiteScope capture.
- `firmware_blob`: the binary writes the ADC channel in bits 9:8 of `adc_control`, where this SoC
  has its oversample field (channel at 5:4): every channel reads channel 0. Reading the live
  `adc_control` value (or disassembling) finds it; the SoC source looks consistent.
- `stale_regs`: `sw/regs.py` was generated from a build with 32-bit CSRs; the shared `soc.json`
  now sets `csr_data_width=8`. Comparing the live register map (`csr.csv`) with `regs.py` finds
  it; the fix is to regenerate it (`sw/gen_regs.py build/sim/csr.csv`).
- `ecpix5_scaler`: as `opaque_gain` with a rev 1.2 netlist (GAIN Q2.14, LIMIT reset 16383).

A task directory has the prompt (`TASK.md`), the initial workspace (`workspace/`), the checker
(`check.py`) and the reference solution (`solution.py`, used to validate the checker); the v2
generators are hidden there too (`opaque_gain/ip_src/gen_ip.py` for the netlists,
`firmware_blob/firmware_src/` for the firmware). Each task has its own TCP port range (prompt:
21x00-21x49 or 22000-22049, checker: 21x50-21x51 or 22051).

## Runner

```sh
export PYTHONPATH=<litex>                         # or an installed LiteX
python3 test/agent_eval/run.py list [--tier v1|v2]
python3 test/agent_eval/run.py setup <task> <workdir>       # fresh workspace, prints the prompt
python3 test/agent_eval/run.py check <task> <workdir>       # JSON result, exit code 0 when passed
python3 test/agent_eval/run.py mcp-config <task> <workdir>  # litex_mcp configuration for the run
python3 test/agent_eval/run.py selftest [--tier v1|v2] [<task> ...]
                                                            # checker fails on the fresh workspace,
                                                            # passes with the reference solution
python3 test/agent_eval/run.py agent <task> shell|mcp <outdir> [--runs 3] [--model M]
                                                            # sequential Claude Code runs
python3 test/agent_eval/run.py score <outdir> [--json]      # pass rate, time, tool calls, cost
```

`selftest` of the offline task runs with the test suite; the simulation tasks need Verilator and
run with `LITEX_AGENT_EVAL_SIM=1 python3 -m pytest test/agent_eval` (about 6 minutes for the 8
simulation tasks, less with `-n 4`; `firmware_blob` alone takes about 2 minutes). The hardware
task runs a dry run (elaboration of the fresh and solved workspaces, no toolchain, no board) when
`litex_boards` is available.

## Hardware Tasks (ECPIX-5)

`ecpix5_scaler` needs a LambdaConcept ECPIX-5 (ECP5-85F), Yosys/nextpnr-ecp5/ecppack,
openFPGALoader and `litex_boards`. The FPGA is only loaded to SRAM (`openFPGALoader -c ft2232
--busdev-num <bus:dev>`), never flashed; the bus:dev selects the board's FT2232 when several FTDI
cables (0403:6010) are connected. The checker builds the reference SoC (about 1-2 minutes),
loads it and talks to it through `litex_server` on the board's FTDI UART.

```sh
export PYTHONPATH=<litex>
# Dry run (no board): elaborate, or build the bitstream without loading it.
python3 test/agent_eval/run.py selftest ecpix5_scaler
LITEX_AGENT_EVAL_HW_BUILD=1 python3 test/agent_eval/run.py selftest ecpix5_scaler

# On the board (lsusb: the ECPIX-5's FT2232 "Dual RS232-HS", e.g. Bus 003 Device 012 -> 3:12).
export LITEX_AGENT_EVAL_HW=ecpix5
export LITEX_AGENT_EVAL_ECPIX5_BUSDEV=<bus:dev>
export LITEX_AGENT_EVAL_ECPIX5_UART=/dev/serial/by-id/usb-FTDI_Dual_RS232-HS-if01-port0  # default
python3 test/agent_eval/run.py selftest ecpix5_scaler      # loads the board twice
python3 test/agent_eval/run.py setup ecpix5_scaler /tmp/eval/ecpix5_scaler  # writes board.env
```

`setup` writes `board.env` (bus:dev and UART) in the workspace for the agent. Only one session
may use the board at a time.

## Run An Agent

Run each task in a fresh workspace outside the LiteX tree, and keep this directory out of the
agent's reach (the checkers and solutions are here): use an installed LiteX (not an editable
install of this tree), a container, or a deny rule for this path.

Example with Claude Code, without and with MCP (same model, same prompt):

```sh
R=<litex>/test/agent_eval/run.py
T=fsm_stuck

# Without MCP: shell tools only, no MCP server.
python3 $R setup $T /tmp/eval/$T-shell > /dev/null
cd /tmp/eval/$T-shell
claude -p "$(cat TASK.md)" --strict-mcp-config --mcp-config '{"mcpServers": {}}' \
    --output-format stream-json --verbose --dangerously-skip-permissions > ../$T-shell.jsonl
python3 $R check $T /tmp/eval/$T-shell > ../$T-shell.check.json

# With MCP: litex_mcp (run mcp-config with a Python that has the MCP SDK, Python >= 3.10).
python3 $R setup $T /tmp/eval/$T-mcp > /dev/null
python3 $R mcp-config $T /tmp/eval/$T-mcp > /tmp/eval/$T-mcp.json
cd /tmp/eval/$T-mcp
claude -p "$(cat TASK.md)" --strict-mcp-config --mcp-config /tmp/eval/$T-mcp.json \
    --output-format stream-json --verbose --dangerously-skip-permissions > ../$T-mcp.jsonl
python3 $R check $T /tmp/eval/$T-mcp > ../$T-mcp.check.json
```

`--dangerously-skip-permissions` is for an unattended run in a disposable environment (container
or VM); otherwise allow the tools explicitly. Other agents: give `TASK.md` as the prompt, the
workspace as the working directory and the `mcp-config` output as the MCP configuration.

## What To Record

Per run (task, condition, model, repetition):

- **pass**: `passed` of `run.py check` (the per-check details say what is still wrong).
- **wall time**: from the start of the agent to its end.
- **tool calls**: number of `tool_use` blocks in the transcript, split MCP (`mcp__litex__*`) /
  shell / file reads and edits.
- **tokens and cost**: input, output and cache tokens, cost (`result` event of the stream-json).
- **cleanup**: `leftover_ports` of `run.py check` (simulation or server left running).

## Scoring

- Run every (task, condition) pair **3 times, sequentially** (runs in parallel contend for CPU and
  distort the wall times), fresh workspace each time: `run.py agent <task> <condition> <outdir>
  --runs 3` does this for Claude Code (workspaces in `<outdir>/work/`).
- Primary: **pass rate** per condition (all tasks, then per tier, then per task).
- Secondary, on passing runs: median **wall time**, median **tool calls split MCP / shell /
  file tools**, median **tokens and cost** (`result` event of the transcript).
- `run.py score <outdir>` prints these per (task, condition) from the transcripts and the check
  results. Report the pairs side by side (per task: shell vs MCP), per tier, with the model and
  the LiteX commit; note leftover processes (`leftover_ports`) separately.
- v1 tasks are a baseline (MCP is not expected to help); the MCP/shell comparison is meaningful on
  v2 tasks, where observation is needed.
