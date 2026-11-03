# Packer test loses packets

This directory contains a simulated LiteX SoC (`target.py`, Verilator) with a test harness of an
8-bit to 32-bit stream packer (`packer.py`, see the `Packer` docstring): a packet generator, the
packer, and a checker that back-pressures the packer output and counts the received packets,
bytes and data errors (see the `PackerTest` docstring). `app.py` is a host application that runs
a test through a `litex_server` and prints the counters.

On this SoC, `app.py` reports `FAIL`: some packets are lost.

Run the SoC and the bridge with:

```sh
./target.py --uart-tcp-port=21600 --output-dir=build/sim [--with-analyzer]
litex_server --uart --uart-port=socket://localhost:21600 --bind-port=21601
./app.py --port=21601
```

`--with-analyzer` adds a LiteScope analyzer on the packer signals (`build/sim/analyzer.csv`).

Find the cause and fix the packer (`packer.py`). The test harness (`target.py`) and the
application are correct and must not be changed (the harness is checked as delivered); the packer
interface (`sink`, `source` and their layouts) must stay the same and the packer must keep
accepting one byte per cycle when its output is not back-pressured.

Constraints: use TCP ports 21600-21649 only, do not touch other running processes, stop the
simulation and the server you started when done.
