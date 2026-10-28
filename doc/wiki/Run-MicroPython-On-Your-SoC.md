You will have a Python prompt on the serial port of your SoC, with the LEDs, the switches and
every register of your cores reachable from it: the LiteX port of
[MicroPython](https://micropython.org/) lives in
[litex-hub/micropython](https://github.com/litex-hub/micropython) (`ports/litex`) and runs on
any SoC with a supported CPU (the RISC-V cores, Mor1kx, LM32). It builds against the headers
of your SoC, like the BIOS does, so the hardware is defined by LiteX and controlled from
Python. Fifteen minutes after [the firmware page](Write-Firmware-For-Your-SoC.md).

## 1. Build the SoC

Any board of [LiteX-Boards](https://github.com/litex-hub/litex-boards), here the Arty with
GPIOs on a Pmod. MicroPython wants about 32 KiB of RAM and 128 KiB for the firmware: a block
RAM main RAM is enough on mid-size FPGAs, otherwise a DRAM.

```sh
python3 -m litex_boards.targets.digilent_arty --with-ethernet --with-pmod-gpio --build --load
```

## 2. Build MicroPython against it

```sh
git clone https://github.com/litex-hub/micropython && cd micropython/ports/litex
export BUILD_DIRECTORY=<path to>/build/digilent_arty       # the headers and the compiler flags of your SoC
make                                                        # build/firmware.bin
```

## 3. Boot it and talk Python

```sh
litex_term /dev/ttyUSB1 --kernel=build/firmware.bin         # or boot.bin on the TFTP server or the SD card
```

```pycon
>>> import litex
>>> litex.leds(0b0101)
>>> import umachine; umachine.freq()
```

Et voilà! `umachine` gives the basics (reset, frequency, identifier) and the `litex` module the
LEDs, the switches and the CSRs. The other boot methods are on the
[firmware page](Write-Firmware-For-Your-SoC.md#4-load-it).

## Notes

- The port is maintained in LiteX-Hub; the older [FuPy](https://fupy.github.io/) port (LM32,
  OpenRISC, 2018 to 2020) and the CircuitPython LiteX port (removed from CircuitPython in
  2021, it targeted the Fomu) are history.
- [MQuickJS on LiteX](https://github.com/enjoy-digital/mquickjs-on-litex) does the same with
  JavaScript: Bellard's engine bare metal on VexRiscv, the CSRs reachable from JavaScript, in
  `litex_sim` and on boards.

## Next

- [Run Zephyr on your SoC](Run-Zephyr-On-Your-SoC.md): an RTOS instead of a prompt.
- [Write firmware for it](Write-Firmware-For-Your-SoC.md): the C the port is built on.
- [OSes ecosystem](OSes-Ecosystem.md): everything that runs on a LiteX SoC.
