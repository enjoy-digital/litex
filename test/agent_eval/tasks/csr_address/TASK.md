# Temperature monitor reads a wrong temperature

This directory contains a simulated LiteX SoC (`target.py`, Verilator) with a temperature sensor
model, and `monitor.py`, a host script that enables the sensor, waits for a conversion and prints
the temperature through a `litex_server`.

The sensor model of the simulation is configured to return 42.19 C (`--sensor-raw=0x2a3`, in 1/16
C), but `monitor.py` prints a very different temperature.

Run the SoC and the bridge with:

```sh
./target.py --uart-tcp-port=21000 --output-dir=build/sim
litex_server --uart --uart-port=socket://localhost:21000 --bind-port=21001
./monitor.py --port=21001
```

Find why the printed temperature is wrong and fix it. The SoC (`target.py`) is correct and must not
be changed; the fixed `monitor.py` must still be runnable as `./monitor.py --port=<port>` from this
directory (the SoC's `csr.csv` is in `build/sim/csr.csv`) and print `temperature: <value> C`.

Constraints: use TCP ports 21000-21049 only, do not touch other running processes, stop the
simulation and the server you started when done.
