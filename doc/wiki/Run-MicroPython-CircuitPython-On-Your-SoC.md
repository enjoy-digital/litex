You can find the LiteX MicroPython port at: https://github.com/litex-hub/micropython/tree/litex-rebase

MicroPython port to the LiteX SoC FPGA framework
================================================

This is a port of MicroPython to the LiteX SoC FPGA framework. LiteX allows easy creation of SoCs
on FPGAs and use of various CPU ISAs/Implementations (VexRiscv, Mor1kx, LM32) and peripherals. By
combining the flexibility of LiteX to define the hardware and the flexibility of MicroPython to
control it, very powerful and flexible systems can be created!

Supported features:
- REPL (Python prompt) over UART.
- Minimal umachine support (reset, freq, identifier).
- Minimal litex support(leds, switches).

Setting up LiteX
-------------------

To install LiteX, please follow the [LiteX installation guide](Installation.md).

Building your LiteX target
-------------------------------
The port of MicroPython to LiteX relies on the software files generated during the target build
that will provides the hardware definition and mapping to MicroPython. To build the MicroPython
firmware, the LiteX target then first needs to be generated. Many FPGA boards are already available
in [LiteX-Boards](https://github.com/litex-hub/litex-boards), in this example, we'll use the Digilent
Arty board:

```bash
$ python3 -m litex_boards.targets.digilent_arty --with-ethernet --with-pmod-gpio --build --load
```
This will build the FPGA SoC, generate the software headers, compile the BIOS/FPGA and load it to the board.

Building MicroPython for your LiteX target
----------------------------------------------------
To build MicroPython for your LiteX target run:
```bash
$ export BUILD_DIRECTORY=build/digilent_arty
$ make
```

Loading MicroPython to your LiteX target
---------------------------------------------------
To load MicroPython for your LiteX target run:
```bash
$ litex_term /dev/ttyUSBX --kernel=build/firmware.bin
```
You can also use TFTP boot from LiteX:
```bash
$ cp build/firmware.bin /tftpboot/boot.bin
```
And just let LiteX boot from it!...

..or use one of the other available boot methods described in [Load Application Code To CPU](Load-Application-Code-To-CPU.md)
