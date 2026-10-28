Your FPGA may already contain a CPU: the Arm cores of a Zynq, a ZynqMP, a Cyclone V or an
Agilex HPS, the Cortex-M of a QuickLogic EOS S3 or a Gowin EMCU, the RISC-V AE350 of a Gowin
GW5AST. LiteX drives them with `--cpu-type=zynq7000`, `zynqmp`, `cyclonev_hps`, `agilex_hps`,
`eos_s3`, `gowin_emcu` or `gowin_ae350`: the LiteX BIOS runs on them and your cores sit on their
bus like on a soft CPU's. The wrappers are in `litex/soc/cores/cpu/*/core.py`, the `hardcore`
category of the [CPU catalog](CPUs.md).

Use the hard CPU when you need its speed (a Cortex-A9 or A53 is ten times a VexRiscv) and
accept the vendor boot flow that comes with it: boot images, clocking and peripheral setup go
through the vendor tools, the LiteX part is the fabric. Orders of magnitude against a
`vexriscv` `standard` at 100 MHz; your clock, memory path and compiler move them:

| CPU | Class | Integer perf. | FP/FLOPS |
| --- | --- | --- | --- |
| `vexriscv` `standard` @ 100MHz | softcore baseline | 1x | soft-float |
| `gowin_emcu` | Cortex-M3 MCU | ~1x | soft-float |
| `eos_s3` | Cortex-M4F MCU | ~1x | single-precision FPU |
| `gowin_ae350` | 32-bit RISC-V MCU/SoC | several x | configuration-dependent |
| `zynq7000` | Cortex-A9 application CPU | 10x+ | VFP/NEON |
| `zynqmp` | Cortex-A53/R5F application/RT CPUs | 10x+ | FP/SIMD |
| `cyclonev_hps` | dual Cortex-A9 application CPU | 10x+ | VFP/NEON |
| `agilex_hps` | Cortex-A53 (Agilex 7), A76+A55 (Agilex 5), A55 (Agilex 3) | 10x+ | FP/SIMD |


## Xilinx Zynq-7000

Demonstrated on [Digilent Zedboard](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/targets/digilent_zedboard.py).
Select with `--cpu-type=zynq7000`. The integration uses the PS7 AXI GP master as the LiteX peripheral/CSR bus and can be configured from a PS7 preset, XCI or target-specific configuration.

One or two Cortex-A9 (up to 1 GHz). A complete Zynq workflow needs a number of vendor tools,
scripts and build steps around the binaries LiteX builds:
[this repository](https://github.com/sergachev/litex-template/tree/main/digilent_zedboard) has
a complete one. The console is on the USB-UART.

## Xilinx UltraScale+ MPSoC

Demonstrated on [Xilinx KV260](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/targets/xilinx_kv260.py).
Select with `--cpu-type=zynqmp`. The integration uses a PS AXI HPM master as the LiteX peripheral/CSR bus and can source a ZynqMP preset from the board target.

Up to four Cortex-A53 (1.5 GHz) and two Cortex-R5F. [litex-template](https://github.com/sergachev/litex-template/)
has a workflow running the BIOS through JTAG. The console is on the USB-UART.

## Intel Cyclone V SoC HPS

Demonstrated on the Terasic DE10-Nano / MiSTer ([target](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/targets/terasic_de10nano.py))
and the DE1-SoC. Select with `--cpu-type=cyclonev_hps`. The HPS-to-FPGA lightweight AXI3
bridge (`h2f_lw`, 2 MB window at `0xff200000`) is the LiteX peripheral/CSR bus, so the Linux
running on the HPS reaches the LiteX gateware through `/dev/mem` (`litex_server --devmem`,
the default window); `add_axi_h2f_master` adds the full-width bridge (`0xc0000000`, 960 MB),
`add_axi_f2h_slave` lets the fabric access the HPS DDR3 (non-coherent below `0x80000000`, L2
coherent through the ACP window above), and `add_fpga2sdram_port` the FPGA-to-SDRAM ports with
the fixed layout expected by MiSTer's preloader/U-Boot. The HPS boots from its own boot ROM and
SD card, so the reset address only places the (optional) BIOS in the HPS DDR3; the 32
FPGA-to-HPS interrupts map to Linux `GIC_SPI 40-71`.


## Intel Agilex HPS

Initial support for the Agilex 3, 5 and 7 HPS: `--cpu-type=agilex_hps --cpu-variant=agilex5`
(or `agilex3`, `agilex7`). The Platform Designer HPS (and optional HPS EMIF) system is
generated at build time from a per-variant configuration table (`add_hps_config` overrides
parameters); the lightweight HPS-to-FPGA AXI4 bridge is the LiteX peripheral bus, with
`add_axi_h2f_master`, `add_axi_f2h_slave` and `add_emif` following the Cyclone V pattern. The
HPS boots through the SDM/FSBL/U-Boot flow of the vendor; the reset address is only used by
the linker. Some parameters are still marked to be verified against a Quartus Pro build.

Agilex 7 has four Cortex-A53, Agilex 5 two Cortex-A76 and two Cortex-A55, Agilex 3 two
Cortex-A55; Quartus Pro is required.

## QuickLogic EOS S3

Demonstrated on [QuickLogic QuickFeather](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/targets/quicklogic_quickfeather.py).
Use `python lib/litex-boards/litex_boards/targets/quicklogic_quickfeather.py --build` with the path to [QORC SDK](https://github.com/QuickLogic-Corp/qorc-sdk) provided in the `QORC_SDK` environment variable to implement. Refer to [this repository](https://github.com/sergachev/litex-template) for an example.
The serial terminal is on pins J3.2/J3.3.

A Cortex-M4F at 80 MHz with 512 KB of SRAM next to a small fabric; the wrapper exposes its
Wishbone interface to the LiteX interconnect.

## Gowin EMCU

Demonstrated on [Sipeed Tang Nano 4K](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/targets/sipeed_tang_nano_4k.py).
To implement, use `python litex-boards/litex_boards/targets/sipeed_tang_nano_4k.py --cpu-type=gowin_emcu --build`.
Program with Gowin Programmer in MCU mode using `project.fs` and `bios.bin`. Look at the [platform file](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/platforms/sipeed_tang_nano_4k.py#L32) for the serial terminal pin locations.

A Cortex-M3 at 80 MHz with its AHB-Lite subsystem next to a small fabric.

## Gowin AE350

Initial support is available for the Gowin AE350 hard RISC-V CPU.
It can be selected with `--cpu-type=gowin_ae350` on supported Gowin targets, including [Sipeed Tang Mega 138K](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/targets/sipeed_tang_mega_138k.py) and [Sipeed Tang Mega 138K Pro](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/targets/sipeed_tang_mega_138k_pro.py).
For example: `python litex-boards/litex_boards/targets/sipeed_tang_mega_138k.py --cpu-type=gowin_ae350 --build`.

An AndesCore A25 RISC-V (up to 800 MHz) with the AE350 peripheral subsystem, reached through
AHB to Wishbone bridges and built with the 32-bit RISC-V toolchain.

## Next

- [Choosing a CPU](Choosing-A-CPU.md): soft or hard, and which soft one.
- [CPUs](CPUs.md): the catalog of the soft CPUs.
- [Control it from the host](Host-Bridges.md): `litex_server --devmem` from the Linux of the hard CPU.
- [Build backends](Build-Backends.md): the vendor toolchains these devices need.
