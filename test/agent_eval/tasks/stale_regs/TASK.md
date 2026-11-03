# Board information application prints wrong values

This directory contains a simulated LiteX SoC (`target.py`, Verilator) with a board information
peripheral (identifier, serial number, calibration, scratch register), and `app.py`, a host
application that prints the board information and tests the scratch register through a
`litex_server` (with the helpers of `sw/`).

The simulated board has the serial number `0x0000a51c00002f17`, a calibration gain of
`0x00010a3d` and an offset of 291, but `app.py` prints other values, a wrong identifier and a
scratch register failure.

Run the SoC and the bridge with:

```sh
./target.py --uart-tcp-port=21800 --output-dir=build/sim
litex_server --uart --uart-port=socket://localhost:21800 --bind-port=21801
./app.py --port=21801
```

Find the cause and fix the host side. The SoC (`target.py`, `soc.json`) is shared with the
hardware targets and must not be changed (it is checked as delivered); `app.py` must still be
runnable as `./app.py --port=<port>` from this directory and keep its output format.

Constraints: use TCP ports 21800-21849 only, do not touch other running processes, stop the
simulation and the server you started when done.
