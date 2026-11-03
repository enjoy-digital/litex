# Sampler firmware reports a channel check failure

This directory contains a simulated LiteX SoC (`target.py`, Verilator) with a VexRiscv CPU, its
BIOS, and a 4-channel ADC model. At boot, the BIOS starts the sampler firmware
(`firmware/sampler.bin`, prebuilt, see `firmware/README.md`) from main RAM. The CPU console is on
a crossover UART, reached (as the SoC's bus) through a UARTBone bridge and a `litex_server`.

The ADC model is configured with 4 different channel values (`--adc-values`), but the firmware
prints `channel check: FAIL`.

Run the SoC, the bridge and the console with:

```sh
./target.py --uart-tcp-port=21700 --output-dir=build/sim
litex_server --uart --uart-port=socket://localhost:21700 --bind-port=21701
litex_term crossover --csr-csv=build/sim/csr.csv --port=21701
```

Find the cause and fix the SoC (`target.py`). The firmware is qualified and frozen: it must not be
changed (the checker boots the delivered binary). Keep the `target.py` command line options and
the ADC register names.

Constraints: use TCP ports 21700-21749 only, do not touch other running processes, stop the
simulation and the server you started when done.
