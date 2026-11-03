---
name: litex-csr-debug
description: Observe and debug a running LiteX SoC through its CSRs (control/status registers) and bus from the host, with litex_server, litex_cli --json or the litex_mcp tools, and add the status registers or counters that answer the next question. Use when a LiteX design misbehaves on a board or in simulation and you need to read or write registers, check the host link, or decide what to instrument.
---

# Debug a LiteX SoC through its registers

Registers before traces: a counter, a sticky flag or an FSM state read from the host answers
most questions without a rebuild per probe.

## 1. Check the link and the SoC first

```sh
litex_server --uart --uart-port=/dev/ttyUSBx --bind-port=1240     # or --jtag, --udp --udp-ip=..., --pcie
litex_cli --csr-csv=build/<board>/csr.csv --port=1240 --ident --json
litex_cli --csr-csv=build/<board>/csr.csv --port=1240 --regs --filter=ctrl --json
```

`ctrl_scratch` reads back `0x12345678` after reset; `ctrl_bus_errors` counts accesses that hit
nothing. With `litex_mcp` (`litex_mcp --csr-csv=build/<board>/csr.csv --port=1240`), call
`litex_check()` first: link, identifier, `ctrl_scratch` and read latency in one result.

## 2. Read

| Need | CLI | MCP tool |
| --- | --- | --- |
| Registers by name | `--regs --filter=<prefix> --json` | `litex_read_registers(filter)` |
| One register | `--read <name or address> --json` | `litex_read_register(name)` |
| Memory | `--read 0x40000000 --length=64 --json` (bytes) | `litex_read_memory(address, length)` (words) |
| What exists | the `csr.csv`/`csr.json` of the build | `litex_list_registers`, `litex_list_memory_regions`, `litex_list_constants` |

`--json` prints one object (`{"schema": 1, ...}`); errors come as `{"error": ...}` with exit
code 1, and a read timeout is an error instead of a silent 0.

## 3. Write (only when the user agreed)

`litex_cli --write <name or address> <value>`; through MCP, `litex_write_register(name, value)` and
`litex_write_memory(address, words)` only exist when the server runs with `--allow-write`. A
write can reset a core, start a DMA or reconfigure a PHY: say what it does before doing it.

## 4. Add the register that answers the question

| Register | Answers |
| --- | --- |
| Counter (events, errors, timeouts) | How often, and does it move when I do X? |
| Sticky flag, cleared by software | Did it ever happen since I last looked? |
| FSM state snapshot | Where is it stuck? |
| History buffer (last N states) | How far did it get? |

In Migen: a `CSRStatus` driven by the signal (`self.errors = CSRStatus(32)`, then
`self.comb += self.errors.status.eq(error_count)`), a `CSRStorage` for a control; signals from
another clock domain cross with `MultiReg` (levels) or `PulseSynchronizer` (events) before the
CSR. Rebuild with `--no-compile` first to see the new names in `csr.csv`.

## Pitfalls

- A client on the default port (1234) can be talking to another board: own `--bind-port`,
  `--ident` before anything else.
- `litex_cli`/`litescope_cli` read `csr.csv` from the current directory unless `--csr-csv` is
  given; the build writes it in `build/<platform>/`. A stale `csr.csv` gives wrong addresses.
- Wide CSRs can break the CSR bus timing on slow fabrics: prefer an index register plus a data
  register.
- Counters in a clock domain that gets reset (recovered clock, PHY domain) clear with it: keep
  bring-up counters reset-less.
- A gateware master reaching CSRs over the main bus needs `self.get_csr_address("name")`;
  `self.csr.address_map(name, origin=True)` is a CSR-local offset.
- Host writes accepted but nothing happens: the transport is fine, look at the bus or the FSM.

## See also

- https://github.com/enjoy-digital/litex/wiki/Debug-A-SoC-On-Hardware#registers-before-traces
- https://github.com/enjoy-digital/litex/wiki/Host-Bridges
- https://github.com/enjoy-digital/litex/wiki/CSR-Bus
- https://github.com/enjoy-digital/litex/wiki/LiteX-for-AI-Agents#drive-a-soc-through-mcp
