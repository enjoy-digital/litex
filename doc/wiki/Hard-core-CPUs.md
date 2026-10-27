LiteX has support for several vendor hard CPU integrations: Xilinx Zynq-7000 (`zynq7000`), Xilinx UltraScale+ MPSoC (`zynqmp`), QuickLogic EOS S3 (`eos_s3`), Gowin EMCU (`gowin_emcu`) and Gowin AE350 (`gowin_ae350`). The CPU wrappers live in `litex/soc/cores/cpu/*/core.py` and are selected with `--cpu-type=<name>`.

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

