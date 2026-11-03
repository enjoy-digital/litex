# LiteX Agent Evaluation

Small debug tasks to measure whether an AI coding agent debugs LiteX SoCs better with the LiteX
MCP server (`litex/tools/litex_mcp.py`) than with the shell tools only (`litex_server`,
`litex_cli --json`, `litescope_cli`, `litex_term`). Each task is a realistic symptom on a small
simulated SoC (Verilator, no hardware, no `sudo`) or on saved toolchain reports, with an automatic
checker.

| Task            | Symptom given to the agent                          | Needs            | Checker                                       |
|-----------------|-----------------------------------------------------|------------------|-----------------------------------------------|
| `csr_address`   | A host script prints a wrong sensor temperature.    | Sim, CSRs        | Reference SoC with another reading, runs the script. |
| `ticker_reset`  | A ticker delay never expires.                       | Sim, CSRs        | Builds the agent's SoC, checks the peripheral against its spec. |
| `fsm_stuck`     | A checksum engine never completes.                  | Sim, LiteScope   | Builds the agent's SoC, runs the engine on 5 lengths/seeds. |
| `bios_memtest`  | The BIOS reports a memory initialization failure.   | Sim, CPU/console | Builds the agent's SoC, checks the boot log and the main RAM. |
| `timing_triage` | Timing triage of a Vivado build (offline).          | Reports          | Compares `answer.json` with the reports.      |

A task directory has the prompt (`TASK.md`), the initial workspace (`workspace/`), the checker
(`check.py`) and the reference solution (`solution.py`, used to validate the checker). Each task
has its own TCP port range (prompt: 21x00-21x49, checker: 21x50-21x51).

## Runner

```sh
export PYTHONPATH=<litex>                         # or an installed LiteX
python3 test/agent_eval/run.py list
python3 test/agent_eval/run.py setup <task> <workdir>       # fresh workspace, prints the prompt
python3 test/agent_eval/run.py check <task> <workdir>       # JSON result, exit code 0 when passed
python3 test/agent_eval/run.py mcp-config <task> <workdir>  # litex_mcp configuration for the run
python3 test/agent_eval/run.py selftest [<task> ...]        # checker fails on the fresh workspace,
                                                            # passes with the reference solution
```

`selftest` of the offline task runs with the test suite; the simulation tasks need Verilator and
run with `LITEX_AGENT_EVAL_SIM=1 python3 -m pytest test/agent_eval` (about 2 minutes, 1 minute with
`-n 4`).

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

- Run every (task, condition) pair at least 3 times, fresh workspace each time.
- Primary: pass rate per condition (all tasks, then per task).
- Secondary, on passing runs: median wall time, median tokens and median tool calls per condition.
- Report the pairs side by side (per task: shell vs MCP), with the model and the LiteX commit.
