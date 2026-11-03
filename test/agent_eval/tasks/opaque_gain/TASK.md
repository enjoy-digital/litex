# Scaler IP returns wrong results

This directory contains a simulated LiteX SoC (`target.py`, Verilator) that integrates the ACME
scaler, a third-party gain/offset IP delivered as a synthesized netlist (`ip/acme_scaler.v`) with
its datasheet (`ip/DATASHEET.md`). The IP registers are mapped on the SoC bus at `0x30000000`.
`driver.py` is the host driver of the IP and `app.py` a host application that configures the IP
(gain 1.5, offset 100), processes a test vector and compares the results with the expected ones,
through a `litex_server`.

On this SoC, `app.py` reports errors on most samples.

Run the SoC and the bridge with:

```sh
./target.py --uart-tcp-port=21500 --output-dir=build/sim
litex_server --uart --uart-port=socket://localhost:21500 --bind-port=21501
./app.py --port=21501
```

Find the cause and fix `driver.py` so that, after `driver.configure(bus, gain, offset)`, the IP
computes `DOUT = min(DIN*gain + offset, 0xffff)` (within 1 LSB) for gains from 0.5 to 4.0 and the
whole 16-bit input range. Only `driver.py` may be changed: the netlist cannot be regenerated and
the SoC (`target.py`, `ip/`) must not be changed (it is checked as delivered). The results must be
computed by the IP, not in software.

Constraints: use TCP ports 21500-21549 only, do not touch other running processes, stop the
simulation and the server you started when done.
