LiteX has support for several vendor hard CPU integrations: Xilinx Zynq-7000 (`zynq7000`), Xilinx UltraScale+ MPSoC (`zynqmp`), Intel Cyclone V SoC HPS (`cyclonev_hps`), Intel Agilex 3/5/7 HPS (`agilex_hps`), QuickLogic EOS S3 (`eos_s3`), Gowin EMCU (`gowin_emcu`) and Gowin AE350 (`gowin_ae350`). The CPU wrappers live in `litex/soc/cores/cpu/*/core.py` and are selected with `--cpu-type=<name>`; they are the `hardcore` category of the [CPUs](CPUs.md) page.

A hard CPU is a processor block already present in the FPGA/SoC silicon. This differs from a softcore CPU, which is synthesized into the FPGA fabric from HDL. Hard CPUs generally have vendor-specific boot, clocking, memory and peripheral configuration flows, while softcores are generated as part of the LiteX gateware.

The common supported use case is running the LiteX BIOS and accessing LiteX CSRs/peripherals from the hard CPU. Full board workflows still depend on vendor tools and board-specific PS/IP configuration, boot-image generation and programming steps.

Hard CPUs are less flexible than softcores, but application-class hard CPUs are generally much more powerful: they can run faster, usually have hardened caches/peripherals and often include hardware floating-point/SIMD support. They are useful when a design needs both FPGA fabric flexibility and more CPU processing than a small softcore can reasonably provide.

The table below gives a rough comparison against a `vexriscv` `standard` softcore running at 100MHz. It is only an order-of-magnitude guide; real results depend on clocking, memory path, caches, compiler options and workload.

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

The characteristics below summarize the hard CPU blocks used by LiteX. Maximum frequencies are vendor/device-family figures; the actual LiteX target clocking can be lower and depends on the exact device, speed grade, board and PS/IP configuration.

# Xilinx Zynq-7000

Demonstrated on [Digilent Zedboard](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/targets/digilent_zedboard.py).
Select with `--cpu-type=zynq7000`. The integration uses the PS7 AXI GP master as the LiteX peripheral/CSR bus and can be configured from a PS7 preset, XCI or target-specific configuration.

Main characteristics: 28nm 7 Series SoC FPGA with a 32-bit Arm Cortex-A9 processing system, single-core on Zynq-7000S devices or dual-core on Zynq-7000 devices, with device-family speeds up to 1GHz.

As any complete workflow on Zynq devices requires a number of tools, scripts and build steps besides the software and gateware binaries built by LiteX, refer to [this repository](https://github.com/sergachev/litex-template/tree/main/digilent_zedboard) for a complete implementation and details.
The serial terminal is on the USB-UART.

# Xilinx UltraScale+ MPSoC

Demonstrated on [Xilinx KV260](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/targets/xilinx_kv260.py).
Select with `--cpu-type=zynqmp`. The integration uses a PS AXI HPM master as the LiteX peripheral/CSR bus and can source a ZynqMP preset from the board target.

Main characteristics: 16nm FinFET+ UltraScale+ MPSoC with up to a quad-core 64-bit Arm Cortex-A53 application processor, a dual-core Arm Cortex-R5F real-time processor and hardened PS peripherals. Vendor maximum clocks are up to 1.5GHz for the Cortex-A53 APU and 600MHz for the Cortex-R5F RPU.

Refer to the readme in [this repository](https://github.com/sergachev/litex-template/) for a workflow allowing execution via JTAG.
The serial terminal is on the USB-UART.

# Intel Cyclone V SoC HPS

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

Main characteristics: 28nm SoC FPGA with a dual-core 32-bit Arm Cortex-A9 (up to 925 MHz),
hardened DDR controller and peripherals, AXI bridges in both directions.

# Intel Agilex HPS

Initial support for the Agilex 3, 5 and 7 HPS: `--cpu-type=agilex_hps --cpu-variant=agilex5`
(or `agilex3`, `agilex7`). The Platform Designer HPS (and optional HPS EMIF) system is
generated at build time from a per-variant configuration table (`add_hps_config` overrides
parameters); the lightweight HPS-to-FPGA AXI4 bridge is the LiteX peripheral bus, with
`add_axi_h2f_master`, `add_axi_f2h_slave` and `add_emif` following the Cyclone V pattern. The
HPS boots through the SDM/FSBL/U-Boot flow of the vendor; the reset address is only used by
the linker. Some parameters are still marked to be verified against a Quartus Pro build.

Main characteristics: Agilex 7 with four Cortex-A53, Agilex 5 with two Cortex-A76 and two
Cortex-A55, Agilex 3 with two Cortex-A55, 64-bit Arm with hardened memory controllers and
peripherals (Quartus Pro required).

# QuickLogic EOS S3

Demonstrated on [QuickLogic QuickFeather](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/targets/quicklogic_quickfeather.py).
Use `python lib/litex-boards/litex_boards/targets/quicklogic_quickfeather.py --build` with the path to [QORC SDK](https://github.com/QuickLogic-Corp/qorc-sdk) provided in the `QORC_SDK` environment variable to implement. Refer to [this repository](https://github.com/sergachev/litex-template) for an example.
The serial terminal is on pins J3.2/J3.3.

Main characteristics: low-power sensor-processing SoC with an Arm Cortex-M4F MCU up to 80MHz, up to 512KB SRAM, a Flexible Fusion Engine and a small embedded programmable-logic block. The LiteX wrapper exposes the EOS S3 Wishbone interface to the LiteX interconnect.

# Gowin EMCU

Demonstrated on [Sipeed Tang Nano 4K](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/targets/sipeed_tang_nano_4k.py).
To implement, use `python litex-boards/litex_boards/targets/sipeed_tang_nano_4k.py --cpu-type=gowin_emcu --build`.
Program with Gowin Programmer in MCU mode using `project.fs` and `bios.bin`. Look at the [platform file](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/platforms/sipeed_tang_nano_4k.py#L32) for the serial terminal pin locations.

Main characteristics: Gowin LittleBee FPGA SoC device with a 32-bit Arm Cortex-M3 hard CPU, an AHB-Lite-style MCU subsystem, on-chip memories and small FPGA fabric. Current GW1NSR-4C datasheets list the Cortex-M3 AHB/APB clocks up to 80MHz.

# Gowin AE350

Initial support is available for the Gowin AE350 hard RISC-V CPU.
It can be selected with `--cpu-type=gowin_ae350` on supported Gowin targets, including [Sipeed Tang Mega 138K](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/targets/sipeed_tang_mega_138k.py) and [Sipeed Tang Mega 138K Pro](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/targets/sipeed_tang_mega_138k_pro.py).
For example: `python litex-boards/litex_boards/targets/sipeed_tang_mega_138k.py --cpu-type=gowin_ae350 --build`.

Main characteristics: GW5AST-138 22nm SRAM FPGA with hardened AndesCore A25 RISC-V CPU IP and AE350 peripheral subsystem, exposed by Gowin as the `RiscV AE350_SOC` hard processor and listed up to 800MHz. The integration exposes the hard CPU to LiteX through AHB/Wishbone bridges and uses a 32-bit RISC-V toolchain.

