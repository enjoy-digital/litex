# Memory initialization fails at boot

This directory contains a simulated LiteX SoC (`target.py`, Verilator) with a VexRiscv CPU, its
BIOS and a 64KiB main RAM. The CPU console is on a crossover UART, reached (as the SoC's bus)
through a UARTBone bridge and a `litex_server`.

At boot, the BIOS reports `Memory initialization failed` and applications loaded in main RAM
crash.

Run the SoC, the bridge and the console with:

```sh
./target.py --uart-tcp-port=21300 --output-dir=build/sim
litex_server --uart --uart-port=socket://localhost:21300 --bind-port=21301
litex_term crossover --csr-csv=build/sim/csr.csv --port=21301
```

Find the cause and fix the target (`target.py`) so that the BIOS boots with a working 64KiB main
RAM; the BIOS is correct and must not be changed, and the main RAM must keep its address and its
64KiB size.

Constraints: use TCP ports 21300-21349 only, do not touch other running processes, stop the
simulation and the server you started when done.
