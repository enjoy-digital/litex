# Cortex-M3

The default `standard` variant uses the Vivado DesignStart FPGA package and
`CortexM3DbgAXI`, as before.

## Experimental generic variant

`--cpu-type=cortex_m3 --cpu-variant=generic` uses the synthesizable
`CORTEXM3INTEGRATIONDS` interface from Cortex-M3 DesignStart Eval (CM3DesignStart
r0p0). It connects the I-Code, D-Code, and System AHB buses through separate
AHB-to-Wishbone bridges to the LiteX interconnect. It contains no FPGA-vendor
primitives and does not use the Vivado AXI wrapper.

Supply your own Arm RTL using `--cpu-rtl-dir=/path/to/rtl`. This directory must
contain both `CORTEXM3INTEGRATIONDS.v` and `cortexm3ds_logic.v` from the
synthesizable package. The Cycle Model wrapper under `cortexm3_model/verilog`
is not a synthesizable processor. LiteX does not download or redistribute Arm
RTL; use the package under its applicable Arm license.

For a Python target, the equivalent is
`CortexM3(platform, variant="generic", rtl_dir="/path/to/rtl")`.

For example, a first test on a DE10-Lite can use only integrated memory:

```sh
python3 -m litex_boards.targets.terasic_de10lite \
    --cpu-type=cortex_m3 --cpu-variant=generic \
    --cpu-rtl-dir=/path/to/rtl \
    --integrated-rom-size=0x20000 --integrated-main-ram-size=0x8000 \
    --sys-clk-freq=50000000 --build
```

Select the serial UART connection appropriate for your board. After loading the
bitstream with the board's normal procedure, check the BIOS banner and ROM CRC,
run the RAM test, and repeat after cold boots and CPU resets. Save the complete
logs, Quartus version, device, and DesignStart package version. Gateware and BIOS
must be rebuilt together.

## Initial scope and validation

- The memory map and software support match the existing M3 variant: ROM at
  `0x00000000`, SRAM at `0x20000000`, main RAM at `0x10000000`, and CSRs at
  `0xa0000000`. The existing software uses polling; this does not extend its
  interrupt support. Two interrupt inputs are connected and the remaining
  DesignStart interrupt inputs are tied low.
- `add_jtag(pads)` enables the core's external JTAG interface. Debug is disabled
  by default. SWD pin sharing and trace outputs are not integrated.
- Clocks run continuously. MPU and low-power entry via WIC are disabled. SysTick
  has no external reference clock; software must select the processor clock.
- `SYSRESETREQ` resets the processor and its bus bridges for at least four
  system clocks. It does not reset the rest of the SoC or the debug power domain.
- The core's local exclusive monitor is used without a global monitor. Software
  must not rely on exclusive operations or bit-band read/modify/write operations
  being atomic against DMA or other bus masters.
- Unit simulations exercise the LiteX bus/control integration, not Arm
  instruction execution. Synthesis and boot with the actual processor RTL on
  non-Xilinx hardware remain to be validated. Cortex-M1 is unchanged.

References: [Arm Eval RTL guide](https://documentation-service.arm.com/static/5e8306ada66ca0336c8cdb30),
[Arm Eval FPGA quick start](https://documentation-service.arm.com/static/5e8306c1a66ca0336c8cdb8e),
[exclusive-access integration guidance](https://support.arm.com/documentation/ka001313/1-0).
