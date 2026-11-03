# Ticker delay never expires

This directory contains a simulated LiteX SoC (`target.py`, Verilator) with a ticker peripheral
(a down-counter, see the `Ticker` docstring), and `app.py`, a host application that arms a
200-tick delay and waits for it to expire, through a `litex_server`.

The ticker is specified to run out of reset in one-shot mode, with a 1000-cycle tick: software
only writes `ticker_load` and then polls `ticker_status.zero`. On this SoC, `app.py` never returns.

Run the SoC and the bridge with:

```sh
./target.py --uart-tcp-port=21100 --output-dir=build/sim
litex_server --uart --uart-port=socket://localhost:21100 --bind-port=21101
./app.py --port=21101
```

Find the cause and fix the gateware (`target.py`) so that the ticker behaves as specified; the
application is correct and must not be changed, and the register map (names and fields) must stay
the same.

Constraints: use TCP ports 21100-21149 only, do not touch other running processes, stop the
simulation and the server you started when done.
