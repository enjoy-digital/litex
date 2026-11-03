---
name: litex-bringup
description: Bring up a LiteX SoC on a new or unfamiliar board, one layer at a time (clock, UART and BIOS, host bridge, DRAM, Ethernet, then the other peripherals), or check the same loop in simulation first. Use when a board does not boot, when adding a board target, or when asked to get a LiteX design running on hardware.
---

# Bring up a LiteX SoC

Add one thing at a time and get a visible result for each before the next: a BIOS prompt, a
register read from the host, a DRAM memtest, a ping.

## 0. The loop in simulation first (no board)

```sh
litex_sim --cpu-type=vexriscv                                         # BIOS prompt in the terminal
litex_sim --uart-name=crossover+uartbone --uart-tcp --uart-tcp-port=2345 --output-dir=build/sim
litex_server --uart --uart-port=socket://localhost:2345 --bind-port=1240
litex_cli --csr-csv=build/sim/csr.csv --port=1240 --ident
```

With `litex_mcp`: `litex_sim_start(args, output_dir)`, `litex_job_wait(job, pattern="litex>")`,
`litex_server_start(["--uart", "--uart-port=socket://localhost:2345", "--bind-port=1240"])`,
`litex_connect(port=1240, csr_csv=...)`, `litex_check()`. With a crossover UART,
`litex_console_read()` returns what the SoC printed.

## 1. Clock, UART, BIOS

- Platform with the clock, the serial port and the LEDs; the `simple` target or the board target
  with no extras: `--build --load`, then `litex_term /dev/ttyUSBx`.
- No output: check the baudrate (`--uart-baudrate`, `litex_term --speed`), the UART pins and the
  clock frequency the PLL receives (`--sys-clk-freq` and the platform's default clock period).

## 2. Host bridge

- `--with-uartbone` (a second UART) or `--uart-name=crossover+uartbone` (console and bridge on one
  port), `--with-jtagbone`, or `--with-etherbone` on Ethernet boards.
- `litex_server --uart --uart-port=/dev/ttyUSBx` (or `--jtag`, `--udp --udp-ip=...`), then
  `litex_cli --csr-csv=build/<board>/csr.csv --ident` and `--regs --filter=ctrl`.
- With a crossover UART, the console goes through the bridge:
  `litex_term crossover --csr-csv=build/<board>/csr.csv`.
- From here every next step can be observed with registers (`litex-csr-debug` skill) and
  LiteScope (`litescope-capture` skill).

## 3. DRAM

- `add_sdram` in the target; the BIOS calibrates and runs the memtest at boot.
- Calibration fails: start at a lower `--sys-clk-freq`, then use the BIOS commands `sdram_cal`,
  `sdram_test`, `sdram_bist` (via `litex_console_command` through MCP, with `--allow-write`).

## 4. Ethernet, then the rest

- `--with-ethernet`: `ping <host-ip>` and `netboot` from the BIOS (`eth_local_ip`/`eth_remote_ip`
  set the addresses); or `--with-etherbone` and `litex_server --udp --udp-ip=<board-ip>`.
- Flash, SD card, PCIe, video: one at a time, each has a BIOS command (`help` lists them).
- Linux only once DRAM is solid.

## Pitfalls

- Several adapters plugged in: select the board's port explicitly; check `--ident` before reading
  anything (a server on the default port 1234 may be another board).
- Use a free `--bind-port` for `litex_server` when another one may be running.
- Shifted strings in the identifier, reads of 0 everywhere: broken bridge or wedged board, fix that
  first.
- `litex_sim --with-ethernet`/`--with-etherbone` need a TAP interface and `sudo`; the crossover +
  TCP UART above does not.
- Do not flash the board while bringing it up: `--load` is enough and is reverted by a power cycle.

## See also

- https://github.com/enjoy-digital/litex/wiki/Add-A-New-Board#3-bring-up-order
- https://github.com/enjoy-digital/litex/wiki/Host-Bridges
- https://github.com/enjoy-digital/litex/wiki/SoC-Simulator
- https://github.com/enjoy-digital/litex/wiki/Debug-A-SoC-On-Hardware
