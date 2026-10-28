You will run a [Zephyr](https://www.zephyrproject.org/) application on your SoC with the
device tree of *your* design: the `litex_vexriscv` and `litex_vexiiriscv` boards and the
`litex` SoC family are upstream in Zephyr, with the drivers of the LiteX cores (LiteUART, the
timer, LiteEth, LiteSPI, LiteI2C, GPIO, PWM, the clock control, the DNA), and LiteX generates
the overlay that maps them to the addresses and interrupts of your SoC. Twenty minutes, with
a Zephyr workspace installed.

## 1. Build a SoC

Zephyr needs the `ecall` instruction and the machine timer: a VexRiscv `lite` variant or
better, or VexiiRiscv. The console and the timer are enough; Ethernet, SPI and I2C are used
when present:

```sh
python3 -m litex_boards.targets.digilent_arty --cpu-type=vexriscv --cpu-variant=standard --with-ethernet --build --load
```

The build writes `build/digilent_arty/csr.json` (always; `--soc-json` to choose the path).

## 2. Generate the device tree overlay and the configuration

```sh
litex_json2dts_zephyr --dts overlay.dts --config overlay.config build/digilent_arty/csr.json
```

The overlay patches the labels of the `litex_vexriscv` board with the addresses and interrupts
of your SoC (`--generate-soc-nodes` writes complete `/soc` nodes instead, for a SoC that
differs a lot from the reference):

```dts
&uart0 {
    reg = <0xf0004000 0x20>;
    interrupts = <0x0 0>;
};
&timer0 {
    reg = <0xf0003800 0x40>;
    interrupts = <0x1 0>;
};
&eth0 {
    reg = <0xf0001000 0x80 0x80000000 0x2000>;
    interrupts = <0x2 0>;
};
&spi0 {
    status = "disabled";
};
&ram0 {
    reg = <0x40000000 0x10000000>;
};
```

and the configuration switches enable the drivers of the cores that exist:

```sh
-DCONFIG_UART_LITEUART=y -DCONFIG_LITEX_TIMER=y -DCONFIG_ETH_LITEETH=y -DCONFIG_SPI_LITESPI=n -DCONFIG_I2C_LITEX=n
```

## 3. Build and run a Zephyr application

```sh
cat overlay.config | xargs west build -b litex_vexriscv samples/subsys/shell/shell_module -- -DDTC_OVERLAY_FILE=overlay.dts
litex_term /dev/ttyUSB1 --kernel=build/zephyr/zephyr.bin
```

The Zephyr shell answers on the serial port. Et voilà! For a VexiiRiscv SoC use
`-b litex_vexiiriscv`. The binary is loaded by the BIOS like any application (serial boot
here, or TFTP, SD card and flash: [the firmware page](Write-Firmware-For-Your-SoC.md#4-load-it)).

## More

- [zephyr-on-litex-vexriscv](https://github.com/litex-hub/zephyr-on-litex-vexriscv) (from
  Antmicro) is the SoC builder of the reference `litex_vexriscv` platform (Arty A7 with the
  F4PGA toolchain, the SDI-MIPI video converter board) and a model of how to script the flow.
- [Renode](SoC-Simulator.md#renode) runs the Zephyr image on a model of the SoC without a
  board, and `litex_sim` in Verilator with `--rom-init` or `--ram-init`.
- NEORV32 has its own upstream Zephyr board; [FreeRTOS](https://github.com/enjoy-digital/freertos-on-litex)
  and NuttX are on the [OSes ecosystem](OSes-Ecosystem.md) page.

## Next

- [Run Linux on your SoC](Run-Linux-On-Your-SoC.md): when an RTOS is not enough.
- [Run MicroPython](Run-MicroPython-On-Your-SoC.md): a Python prompt on the same SoC.
- [OSes ecosystem](OSes-Ecosystem.md): Zephyr next to FreeRTOS, NuttX and the others.
- [Tools](Tools.md#exporting-the-soc-description): `litex_json2dts_zephyr` and its siblings.
