# Scaler IP returns wrong results on the ECPIX-5

This directory contains a LiteX SoC for the LambdaConcept ECPIX-5 board (`target.py`, ECP5-85F,
based on the `litex_boards` ECPIX-5 target) that integrates the ACME scaler, a third-party
gain/offset IP delivered as a synthesized netlist (`ip/acme_scaler.v`) with its datasheet
(`ip/DATASHEET.md`). The IP registers are mapped on the SoC bus at `0x90000000`. The CPU console
is on a crossover UART and the SoC's bus is reached through a UARTBone bridge on the board's FTDI
UART. `driver.py` is the host driver of the IP and `app.py` a host application that configures the
IP (gain 1.5, offset 100), processes a test vector and compares the results with the expected
ones, through a `litex_server`.

On the board, `app.py` reports errors on most samples.

`board.env` gives the board access: `ECPIX5_BUSDEV`, the USB bus:dev of the board's FT2232 (JTAG,
several identical FTDI cables are connected to this host), and `ECPIX5_UART`, the serial port of
its UART. Build, load (to SRAM), run the bridge and the application with:

```sh
. ./board.env
./target.py --uart-name=crossover --with-uartbone --output-dir=build/ecpix5 --build --load --busdev=$ECPIX5_BUSDEV
litex_server --uart --uart-port=$ECPIX5_UART --uart-baudrate=115200 --bind-port=22001
./app.py --port=22001
```

Find the cause and fix `driver.py` so that, after `driver.configure(bus, gain, offset)`, the IP
computes `DOUT = min(DIN*gain + offset, 0xffff)` (within 1 LSB) for gains from 0.5 to 3.5 and the
whole 16-bit input range. Only `driver.py` may be changed: the netlist cannot be regenerated and
the SoC (`target.py`, `ip/`) must not be changed (it is checked as delivered). The results must be
computed by the IP, not in software.

Constraints: load the FPGA SRAM only, never the SPI flash (no `--flash`, no openFPGALoader `-f`);
only use the FT2232 at `$ECPIX5_BUSDEV` and the serial port `$ECPIX5_UART` (other boards are
connected to this host); use TCP ports 22000-22049 only; do not touch other running processes;
stop the server you started when done.
