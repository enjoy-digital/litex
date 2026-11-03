# Checksum engine never completes

This directory contains a simulated LiteX SoC (`target.py`, Verilator) with a checksum engine (see
the `ChecksumEngine` docstring), and `app.py`, a host application that runs the engine on a
block of 1000 words and compares the result with the expected sum, through a `litex_server`.

On this SoC, `app.py` reports an engine timeout: `engine_status.busy` stays at 1 and the run never
completes.

Run the SoC and the bridge with:

```sh
./target.py --uart-tcp-port=21200 --output-dir=build/sim [--with-analyzer]
litex_server --uart --uart-port=socket://localhost:21200 --bind-port=21201
./app.py --port=21201
```

`--with-analyzer` adds a LiteScope analyzer on the engine signals (`build/sim/analyzer.csv`).

Find the cause and fix the gateware (`target.py`); the application is correct and must not be
changed, and the register map must stay the same. The engine must work for any length from 1 to
65535 words.

Constraints: use TCP ports 21200-21249 only, do not touch other running processes, stop the
simulation and the server you started when done.
