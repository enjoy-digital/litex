You can run [Zephyr RTOS](https://github.com/zephyrproject-rtos/zephyr) on your LiteX SoC!

### Generate VexRiscv/LiteX SoC

First generate a SoC with a supported VexRiscv CPU. Please note that since Zephyr requires `ecall` instruction support, you need at least the `lite` variant of the CPU.

```
./litex-boards/litex_boards/targets/digilent_arty.py --cpu-type vexriscv --with-ethernet --csr-json csr.json
```

### Generate Zephyr configuration and DTS overlay

In order to build Zephyr image that is compatible with the hardware platform you need to generate additional file. Thankfully, LiteX comes with helper scripts:

```
./litex/litex/tools/litex_json2dts_zephyr.py --dts overlay.dts --config overlay.config csr.json
```

As a result you'll get the DTS overlay file, similar to:
```
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
&i2c0 {
    status = "disabled";
};
&ram0 {
    reg = <0x40000000 0x10000000>;
};
&dna0 {
    reg = <0xf0002000 0x100>;
};
```

and Zephyr config switches like:
```
-DCONFIG_UART_LITEUART=y -DCONFIG_LITEX_TIMER=y -DCONFIG_ETH_LITEETH=y -DCONFIG_SPI_LITESPI=n -DCONFIG_I2C_LITEX=n
```

### Build Zephyr example application

Now you can build a Zephyr binary:
```
cat overlay.config | xargs west build \
	-b litex_vexriscv \
	samples/subsys/shell/shell_module \
	-- \
	-DDTC_OVERLAY_FILE=overlay.dts
```

### More details

For more details and scripts to automate the process please take a look at: [The LiteX Build Environment Wiki page](https://github.com/timvideos/litex-buildenv/wiki/Zephyr) and the [build-zephyr.sh](https://github.com/timvideos/litex-buildenv/blob/master/scripts/build-zephyr.sh) script.
