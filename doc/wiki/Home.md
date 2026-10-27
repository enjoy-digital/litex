<p align="center"><img src="https://raw.githubusercontent.com/enjoy-digital/litex/master/doc/litex.png"></p>

```
             Copyright 2012-2026 / Enjoy-Digital & LiteX developers
```
[![](https://github.com/enjoy-digital/litex/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litex/actions)
![License](https://img.shields.io/badge/License-BSD%202--Clause-orange.svg)

# Welcome to LiteX!

The LiteX framework provides a convenient and efficient infrastructure to create FPGA Cores/SoCs, to explore various digital design architectures and create [full FPGA based systems](Projects.md).

**LiteX SoC builder framework quick tour/overview: [Slides](https://docs.google.com/presentation/d/1mQOWqgmyQxpjLAzFwCulqgkp0TuxmaIDYp5iUfPqqIk/edit?usp=sharing)**

**Want to get started and/or looking for documentation? Make sure to visit the [Wiki](Home.md)!**

**Want development notes from building FPGA SoCs with LiteX? Visit the [LiteX Notes blog](https://enjoy-digital.github.io/)!**

**A question or want to get in touch? Join us on [Discord](https://discord.gg/PkJwjDbxeG) or on our IRC channel: [#litex at irc.libera.chat]**.

LiteX provides all the common components required to easily create an FPGA Core/SoC:
 - :heavy_check_mark: Buses and Streams (Wishbone, AXI, Avalon-ST) and their interconnect.
 - :heavy_check_mark: Simple cores: RAM, ROM, Timer, UART, JTAG, GPIO, SPI, I2C, PWM, video, USB, HyperRAM, etc...
 - :heavy_check_mark: Complex cores through the ecosystem of cores: [LiteDRAM](https://github.com/enjoy-digital/litedram), [LitePCIe](https://github.com/enjoy-digital/litepcie), [LiteEth](https://github.com/enjoy-digital/liteeth), [LiteSATA](https://github.com/enjoy-digital/litesata), [LiteNVMe](https://github.com/enjoy-digital/litenvme), etc...
 - :heavy_check_mark: Various CPUs & ISAs: RISC-V (VexRiscv, VexiiRiscv, NaxRiscv, Rocket, SERV, ...), OpenRISC, LM32, POWER, MIPS, the hard CPUs of Zynq, Agilex and Cyclone V, X86 (through a PCIe), etc...
 - :heavy_check_mark: Mixed languages support with VHDL/Verilog/SystemVerilog/Amaranth/Spinal-HDL/etc... integration capabilities.
 - :heavy_check_mark: Powerful debug infrastructure through the various [bridges](Use-Host-Bridge-to-control-debug-a-SoC.md) and [LiteScope](https://github.com/enjoy-digital/litescope).
 - :heavy_check_mark: Direct/Fast simulation through [Verilator](https://www.veripool.org/verilator/).
 - :heavy_check_mark: Build backends for open-source and vendor toolchains (Xilinx, Intel, Lattice, Gowin, Efinix, CologneChip, Anlogic, Microsemi, QuickLogic).
 - :heavy_check_mark: And a lot more... :)

# Typical LiteX design flow:
```
                                      +---------------+
                                      |FPGA toolchains|
                                      +----^-----+----+
                                           |     |
                                        +--+-----v--+
                       +-------+        |           |
                       | Migen +-------->           |
                       +-------+        |           |        Your design
                                        |   LiteX   +---> ready to be used!
                                        |           |
              +----------------------+  |           |
              |LiteX Cores Ecosystem +-->           |
              +----------------------+  +-^-------^-+
               (Eth, SATA, DRAM, USB,     |       |
                PCIe, Video, etc...)      +       +
                                         board   target
                                         file    file
```
Your design is two Python files: the *platform* describes the board (pins, clocks, connectors, toolchain, programmer; [LiteX-Boards](https://github.com/litex-hub/litex-boards) has 200+ of them) and the *target* describes your SoC (CPU, memories, peripherals, cores from the ecosystem). The LiteX Builder generates the Verilog and constraints, runs the toolchain (or Verilator), builds the BIOS and generates the software support (`csr.h`, `soc.h`, `mem.h`, `memory.x`, `csr.csv/json/svd`, device trees); the host tools (`litex_term`, `litex_server`/`litex_cli` through a UART, JTAG, Ethernet or PCIe bridge, LiteScope, GDB) control and debug the running SoC.

By combining LiteX with the ecosystem of cores, creating complex SoCs becomes a lot easier than with traditional approaches while providing better portability and flexibility: Here is for example a Multi-core Linux Capable SoC based on VexRiscv-SMP CPU, LiteDRAM, LiteSATA built and integrated with LiteX, running on a cheap repurposed [Acorn CLE215+ Mining Board](Use-LiteX-on-the-Acorn-CLE-215.md):
![](https://user-images.githubusercontent.com/1450143/103343266-f8cc9a00-4a8b-11eb-9444-f02e1522a490.png)
For more info, have a look at [Linux-on-LiteX-Vexriscv](https://github.com/litex-hub/linux-on-litex-vexriscv) project and try running Linux on your FPGA board!

LiteX's digital logic is currently described with [Migen](https://github.com/m-labs/migen) which does not prevent users to create mixed language projects:
- It's very common and easy to integrate VHDL/Verilog/SystemVerilog/Amaranth/Spinal-HDL code in LiteX!
- It's also very common to do the opposite and generate the LiteX design as a verilog file and integrate it in a traditional flow.

LiteX was initially developed by [Enjoy-Digital](http://enjoy-digital.fr/) to create projects for clients (and we are still using it for that :)) and trying to take the different clients' requirements/needs consideration made, we think, the framework very flexible:
 - Some users only want to use it to easily interconnect their existing VHDL/Verilog/SV cores.
 - Some users are only interested to reuse the PCIe/Ethernet/SATA/etc cores as regular core and just integrate them in their traditional flow.
 - Some users with a hardware background start with the above approaches and then switch later to the full Python flow since find it more efficient.
 - Some users with a software background and fluent with Python start playing with FPGAs while they would probably never touch FPGA otherwise :)
 - Etc...

We are well aware that everyone has a different background, so it's up to you to pick the right approach with LiteX that will be convenient for you! [The LiteX approach](LiteX-Approach.md) describes the way we build with it.

We share this project under a permissive BSD 2-Clause License, inspired by our fantastic community and supportive clients. If LiteX benefits your research, hobby, or commercial projects, we kindly ask for your positive collaboration and respect for the effort involved. The framework is also far from perfect and we'll be happy to have your [feedback or/and contributions](Feedback-Contribution-Support.md). Have fun! :wink:

# Where to go next

| | |
| --- | --- |
| **Get started** | [Installation](Installation.md), [SoC Simulator](SoC-Simulator.md) (no board needed), [Create a minimal SoC](Create-A-minimal-SoC.md), [Load application code](Load-Application-Code-To-CPU.md), [Tutorials and resources](Tutorials-Resources.md) |
| **Understand** | [The LiteX approach](LiteX-Approach.md), [LiteX for Hardware Engineers](LiteX-for-Hardware-Engineers.asciidoc), [SoC builder](SoC-builder.md), [CPUs](CPUs.md), [Wishbone](Wishbone-Bus.md) / [AXI](AXI-Bus.md) / [CSR](CSR-Bus.md) buses, [Streams](Streams.md), [Cores](Cores.md), [Build backends](Build-Backends.md), [Migen and Amaranth](Migen-Amaranth.md) |
| **Build** | [Add a new board](Add-A-New-Board.md), [Add a new core](Add-A-New-Core.md), [Add a new CPU](Add-A-New-CPU.md), [Reuse a Verilog/VHDL/Amaranth/SpinalHDL core](Reuse-a-SystemVerilog-VHDL-Amaranth-Spinal-HDL-Chisel-core.md), [Create a complex SoC](Create-A-complex-SoC-With-Cores-From-The-Ecosystem.md), [Create a PCIe SoC](Create-A-PCIe-SoC.md), [Export a core/SoC to Verilog](Export-Your-Core-SoC-To-Verilog.md) |
| **Debug** | [Host bridges](Use-Host-Bridge-to-control-debug-a-SoC.md), [LiteScope](Use-LiteScope-To-Debug-A-SoC.md), [GDB over JTAG](JTAG-GDB-Debugging-with-VexRiscv-CPU.md), [SoC documentation](SoC-Documentation.md) |
| **Run software** | [OSes ecosystem](OSes-Ecosystem.md): [Linux](Run-Linux-On-Your-SoC.md), [Zephyr](Run-Zephyr-On-Your-SoC.md), [MicroPython](Run-MicroPython-CircuitPython-On-Your-SoC.md), [Renode](Generate-Renode-simulation.md) |
| **Community** | [Projects built with LiteX](Projects.md), [Cores ecosystem](Cores-Ecosystem.md), [Feedback, contribution, support](Feedback-Contribution-Support.md), [Contributing to this wiki](Contributing-to-the-Wiki.md) |

# The ecosystem

![The LiteX ecosystem: the framework, the cores, the CPUs, the boards, the software and the host tools](images/litex-ecosystem-map.svg)

LiteX already supports various soft CPUs (VexRiscv, VexiiRiscv, NaxRiscv, Rocket, Microwatt, SERV, Mor1kx, LM32, PicoRV32, BlackParrot, ...), the hard CPUs of Zynq, Agilex and Cyclone V, and is compatible with the LiteX cores ecosystem:

| Name | Build Status | Description |
| --- | --- | --- |
| [LiteX-Boards](http://github.com/litex-hub/litex-boards) | [![](https://github.com/litex-hub/litex-boards/workflows/ci/badge.svg)](https://github.com/litex-hub/litex-boards/actions) | Boards support |
| [LiteDRAM](http://github.com/enjoy-digital/litedram) | [![](https://github.com/enjoy-digital/litedram/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litedram/actions) | DRAM |
| [LiteEth](http://github.com/enjoy-digital/liteeth) | [![](https://github.com/enjoy-digital/liteeth/workflows/ci/badge.svg)](https://github.com/enjoy-digital/liteeth/actions) | Ethernet |
| [LitePCIe](http://github.com/enjoy-digital/litepcie) | [![](https://github.com/enjoy-digital/litepcie/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litepcie/actions) | PCIe |
| [LiteNVMe](http://github.com/enjoy-digital/litenvme) | [![](https://github.com/enjoy-digital/litenvme/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litenvme/actions) | NVMe |
| [LiteSATA](http://github.com/enjoy-digital/litesata) | [![](https://github.com/enjoy-digital/litesata/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litesata/actions) | SATA |
| [LiteSDCard](http://github.com/enjoy-digital/litesdcard) | [![](https://github.com/enjoy-digital/litesdcard/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litesdcard/actions) | SD card / eMMC |
| [LiteICLink](http://github.com/enjoy-digital/liteiclink) | [![](https://github.com/enjoy-digital/liteiclink/workflows/ci/badge.svg)](https://github.com/enjoy-digital/liteiclink/actions) | Inter-Chip communication |
| [LiteJESD204](http://github.com/enjoy-digital/litejesd204) | [![](https://github.com/enjoy-digital/litejesd204/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litejesd204/actions) | JESD204B/JESD204C |
| [LiteDSP](http://github.com/enjoy-digital/litedsp) | [![](https://github.com/enjoy-digital/litedsp/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litedsp/actions) | RF/DSP blocks (WIP) |
| [LiteSPI](http://github.com/litex-hub/litespi) | [![](https://github.com/litex-hub/litespi/workflows/ci/badge.svg)](https://github.com/litex-hub/litespi/actions) | SPI/SPI-Flash |
| [LiteI2C](http://github.com/litex-hub/litei2c) | [![](https://github.com/litex-hub/litei2c/workflows/ci/badge.svg)](https://github.com/litex-hub/litei2c/actions) | I2C |
| [LiteScope](http://github.com/enjoy-digital/litescope) | [![](https://github.com/enjoy-digital/litescope/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litescope/actions) | Logic analyzer |

Details, supported standards and hardware: [Cores ecosystem](Cores-Ecosystem.md).

# Examples of designs built with LiteX

Custom PCIe SDI Capture/Playback board built around LitePCIe and integrated with LiteX, allowing full control of the SDI flow and very low latency.
![](https://user-images.githubusercontent.com/1450143/103343791-282fd680-4a8d-11eb-82bd-c068ac1ad293.png)
Alternative firmware/gateware for the SDS1104X-E Scope:
![enter image description here](https://user-images.githubusercontent.com/1450143/124901562-6977e480-dfe2-11eb-9071-4344d1146968.png)
HBM2 test infrastructure on Forest Kitten 33:
![enter image description here](https://user-images.githubusercontent.com/1450143/124902018-d4c1b680-dfe2-11eb-89c4-8b498605c34d.png)

Recent systems built with LiteX and documented the same way: [TriXium](https://github.com/enjoy-digital/trixium) (ternary LLMs decoded on FPGA cards), [LiteX-M2SDR](https://github.com/enjoy-digital/litex_m2sdr) (an M.2 software defined radio), [USB3-PIPE](https://github.com/enjoy-digital/usb3_pipe) (USB 3.0 without external chip), [LiteX-WR-NIC](https://github.com/enjoy-digital/litex_wr_nic) (a White Rabbit NIC). To discover more products/projects built with LiteX, visit the [projects page](Projects.md).

# Sponsors/Partners

A huge shoutout to our awesome industrial clients who have given us the green light to incorporate some of the developments we initially created for them directly into LiteX! These innovative developments often provide the building blocks for the features that the wider community can then use and improve upon. Your support has been instrumental for the project, and we are incredibly grateful for your partnership. Thanks!

# Papers, Presentations, Tutorials, Links

**FPGA lessons/tutorials:** https://github.com/litex-hub/fpga_101 (and the [Tutorials and resources](Tutorials-Resources.md) page).

**Migen tutorial:** https://m-labs.hk/migen/manual

**OSDA 2019 paper/slides:** https://osda.gitlab.io/19/1.1.pdf, https://osda.gitlab.io/19/1.1-slides.pdf

**Linux on LiteX-Vexriscv:** https://github.com/litex-hub/linux-on-litex-vexriscv

**LiteX vs. Vivado First Impressions:** https://www.bunniestudios.com/blog/?p=5018

**35C3 - Snakes and Rabbits - How CCC shaped an open hardware success:** https://www.youtube.com/watch?v=AlmVxR0417c

**Tim has too many projects - LatchUp Edition:** https://www.youtube.com/watch?v=v7WrTmexod0

# Sub-packages

**litex.gen:** specific or experimental modules to generate HDL that are not integrated in Migen.

**litex.build:** tools to build FPGA bitstreams (interface to vendor and open-source toolchains) and to simulate HDL code or full SoCs.

**litex.soc:** definitions/modules to build cores (buses, CSRs, streams), the cores, the CPUs, the SoC builder and the software (BIOS, libraries).

**litex.tools:** the host tools (`litex_term`, `litex_server`, `litex_cli`, `litex_sim`, generators and exporters).

# Quick start guide

```sh
python3 -m venv ~/litex-venv && source ~/litex-venv/bin/activate
wget https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py
chmod +x litex_setup.py
./litex_setup.py --init --install --config=standard   # Migen, LiteX, the cores, the boards, the CPUs
./litex_setup.py --gcc=riscv                           # the RISC-V compiler for the BIOS and software
pip3 install meson ninja
litex_sim --cpu-type=vexriscv                          # a SoC in Verilator, no board needed
```

The complete guide (toolchains, boards, updates, troubleshooting): [Installation](Installation.md).

# Community

<p align="center"><img src="https://raw.githubusercontent.com/enjoy-digital/litex/master/doc/litex-hub.png" width="400"></p>

Over the years a friendly community has grown around LiteX and the ecosystem of cores. Feedbacks and contributions have already greatly improved the project, EnjoyDigital still leads the development but it is now a community project and collaborative projects created around/with LiteX can be found at https://github.com/litex-hub.

# Contact

E-mail: florent@enjoy-digital.fr
