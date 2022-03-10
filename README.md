<p align="center"><img src="https://raw.githubusercontent.com/enjoy-digital/litex/master/doc/litex.png"></p>

```
             Copyright 2012-2022 / Enjoy-Digital & LiteX developers
```
[![](https://github.com/enjoy-digital/litex/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litex/actions)
![License](https://img.shields.io/badge/License-BSD%202--Clause-orange.svg)

# Welcome to LiteX!


The LiteX framework provides a convenient and efficient infrastructure to create FPGA Cores/SoCs, to explore various digital design architectures and create [full FPGA based  systems](https://github.com/enjoy-digital/litex/wiki/Projects).

**LiteX SoC builder framework quick tour/overview: [Slides](https://docs.google.com/presentation/d/1mQOWqgmyQxpjLAzFwCulqgkp0TuxmaIDYp5iUfPqqIk/edit?usp=sharing)**

**Want to get started and/or looking for documentation? Make sure to visit the [Wiki](https://github.com/enjoy-digital/litex/wiki)!**

**A question or want to get in touch? Our IRC channel is [#litex at irc.libera.chat]**.

LiteX provides all the common components required to easily create an FPGA Core/SoC:
 - :heavy_check_mark: Buses and Streams (Wishbone, AXI, Avalon-ST) and their  interconnect.
 - :heavy_check_mark: Simple cores: RAM, ROM, Timer, UART, JTAG, etc….
 - :heavy_check_mark: Complex cores through the ecosystem of cores: [LiteDRAM](https://github.com/enjoy-digital/litedram), [LitePCIe](https://github.com/enjoy-digital/litepcie), [LiteEth](https://github.com/enjoy-digital/liteeth), [LiteSATA](https://github.com/enjoy-digital/litesata), etc...
 - :heavy_check_mark: Various CPUs & ISAs: RISC-V, OpenRISC, LM32, Zynq, X86 (through a PCIe), etc...
 - :heavy_check_mark: Mixed languages support with VHDL/Verilog/(n)Migen/Spinal-HDL/etc... integration capabilities.
 - :heavy_check_mark: Powerful debug infrastructure through the various [bridges](https://github.com/enjoy-digital/litex/wiki/Use-Host-Bridge-to-control-debug-a-SoC) and [Litescope](https://github.com/enjoy-digital/litescope).
 - :heavy_check_mark: Direct/Fast simulation through [Verilator](https://www.veripool.org/verilator/).
 - :heavy_check_mark: Build backends for open-source and vendors toolchains.
 - :heavy_check_mark: And a lot more... :)

By combining LiteX with the ecosystem of cores, creating complex SoCs becomes a lot easier than with traditional approaches while providing better portability and flexibility: Here is for example a Multi-core Linux Capable SoC based on VexRiscv-SMP CPU, LiteDRAM, LiteSATA built and integrated with LiteX, running on a cheap repurposed [Acorn CLE215+ Mining Board](https://github.com/enjoy-digital/litex/wiki/Use-LiteX-on-the-Acorn-CLE-215):
![](https://user-images.githubusercontent.com/1450143/103343266-f8cc9a00-4a8b-11eb-9444-f02e1522a490.png)
For more info, have a look at [Linux-on-LiteX-Vexriscv](https://github.com/litex-hub/linux-on-litex-vexriscv) project and try running Linux on your FPGA board!

LiteX's digital logic is currently described with [Migen](https://github.com/m-labs/migen) which does not prevent users to create mixed language projects:
- It's very common and easy to integrate VHDL/Verilog/SystemVerilog/nMigen/Spinal-HDL code in LiteX!
- It's also very common to do the opposite and generate the LiteX design as a verilog file and integrate it in a traditional flow.


LiteX was initially developed by [Enjoy-Digital](http://enjoy-digital.fr/) to create projects for clients (and we are still using it for that :)) and trying to take the different clients' requirements/needs consideration made, we think, the framework very flexible:
 - Some users only want to use it to easily interconnect their existing VHDL/Verilog/SV cores.
 - Some users are only interested to reuse the PCIe/Ethernet/SATA/etc cores as regular core and just integrate them in their traditional flow.
 - Some users with a hardware background start with the above approaches and then switch later to the full Python flow since find it more efficient.
 - Some users with a software background and fluent with Python start playing with FPGAs while they would probably never touch FPGA otherwise :)
 - Etc...

We are well aware that everyone has a different background, so it's up to you to pick the right approach with LiteX that will be convenient for you!

To get started we encourage you to read the [wiki](https://github.com/enjoy-digital/litex/wiki).

You already have a FPGA board(s)? Visit [LiteX-Boards](https://github.com/litex-hub/litex-boards) to see if your board(s) is already supported!

The framework is also far from perfect and we'll be happy to have your [feedback or/and contributions](https://github.com/enjoy-digital/litex/wiki/Feedback-Contribution-Support).

Have fun! :wink:

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
LiteX already supports various softcores CPUs: VexRiscv, Rocket, LM32, Mor1kx, PicoRV32, BlackParrot and is compatible with the LiteX's Cores Ecosystem:

| Name                                                         | Build Status                                                                                                                       | Description               |
| ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| [LiteX-Boards](http://github.com/litex-hub/litex-boards)     | [![](https://github.com/litex-hub/litex-boards/workflows/ci/badge.svg)](https://github.com/litex-hub/litex-boards/actions)         | Boards support            |
| [LiteDRAM](http://github.com/enjoy-digital/litedram)         | [![](https://github.com/enjoy-digital/litedram/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litedram/actions)         | DRAM                      |
| [LiteEth](http://github.com/enjoy-digital/liteeth)           | [![](https://github.com/enjoy-digital/liteeth/workflows/ci/badge.svg)](https://github.com/enjoy-digital/liteeth/actions)           | Ethernet                  |
| [LitePCIe](http://github.com/enjoy-digital/litepcie)         | [![](https://github.com/enjoy-digital/litepcie/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litepcie/actions)         | PCIe                      |
| [LiteSATA](http://github.com/enjoy-digital/litesata)         | [![](https://github.com/enjoy-digital/litesata/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litesata/actions)         | SATA                      |
| [LiteSDCard](http://github.com/enjoy-digital/litesdcard)     | [![](https://github.com/enjoy-digital/litesdcard/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litesdcard/actions)     | SD card                   |
| [LiteICLink](http://github.com/enjoy-digital/liteiclink)     | [![](https://github.com/enjoy-digital/liteiclink/workflows/ci/badge.svg)](https://github.com/enjoy-digital/liteiclink/actions)     | Inter-Chip communication  |
| [LiteJESD204B](http://github.com/enjoy-digital/litejesd204b) | [![](https://github.com/enjoy-digital/litejesd204b/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litejesd204b/actions) | JESD204B                  |
| [LiteSPI](http://github.com/litex-hub/litespi)               | [![](https://github.com/litex-hub/litespi/workflows/ci/badge.svg)](https://github.com/litex-hub/litespi/actions)                   | SPI/SPI-Flash               |
| [LiteScope](http://github.com/enjoy-digital/litescope)       | [![](https://github.com/enjoy-digital/litescope/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litescope/actions)       | Logic analyzer            |

# Examples of designs built with LiteX:
Custom PCIe SDI Capture/Playback board built around LitePCIe and integrated with LiteX, allowing full control of the SDI flow and very low latency.
![](https://user-images.githubusercontent.com/1450143/103343791-282fd680-4a8d-11eb-82bd-c068ac1ad293.png)
Alternative firmware/gateware for the SDS1104X-E Scope:
![enter image description here](https://user-images.githubusercontent.com/1450143/124901562-6977e480-dfe2-11eb-9071-4344d1146968.png)
HBM2 test infrastructure on Forest Kitten 33:
![enter image description here](https://user-images.githubusercontent.com/1450143/124902018-d4c1b680-dfe2-11eb-89c4-8b498605c34d.png)

To discover more products/projects built with LiteX, visit the [projects page](https://github.com/enjoy-digital/litex/wiki/Projects) on the Wiki.

# Papers, Presentations, Tutorials, Links
**FPGA lessons/tutorials:**
- https://github.com/enjoy-digital/fpga_101

**Migen tutorial:**
- https://m-labs.hk/migen/manual

**OSDA 2019 paper/slides:**
- https://osda.gitlab.io/19/1.1.pdf
- https://osda.gitlab.io/19/1.1-slides.pdf

**Linux on LiteX-Vexriscv:**
- https://github.com/litex-hub/linux-on-litex-vexriscv

**RISC-V Getting Started Guide:**
- https://risc-v-getting-started-guide.readthedocs.io/en/latest/

**LiteX vs. Vivado First Impressions:**
- https://www.bunniestudios.com/blog/?p=5018

**35C3 - Snakes and Rabbits - How CCC shaped an open hardware success:**
- https://www.youtube.com/watch?v=AlmVxR0417c

**Tim has to many projects - LatchUp Edition:**
https://www.youtube.com/watch?v=v7WrTmexod0


# Sub-packages
**litex.gen**
Provides specific or experimental modules to generate HDL that are not integrated in Migen.

**litex.build:**
Provides tools to build FPGA bitstreams (interface to vendor toolchains) and to simulate HDL code or full SoCs.

**litex.soc:**
Provides definitions/modules to build cores (bus, bank, flow), cores and tools to build a SoC from such cores.

# Quick start guide
1. Install Python 3.6+ and FPGA vendor's development tools and/or [Verilator](http://www.veripool.org/).
2. Install Migen/LiteX and the LiteX's cores:

```sh
$ wget https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py
$ chmod +x litex_setup.py
$ ./litex_setup.py --init --install --user (--user to install to user directory) --config=(minimal, standard, full)
```
  Later, if you need to update all repositories:
```sh
$ ./litex_setup.py --update
```

> **Note:** On MacOS, make sure you have [HomeBrew](https://brew.sh) installed. Then do, ``brew install wget``.

> **Note:** On Windows, it's possible you'll have to set `SHELL` environment variable to `SHELL=cmd.exe`.

3. Install a RISC-V toolchain (Only if you want to test/create a SoC with a CPU):
```sh
$ pip3 install meson ninja
$ ./litex_setup.py --gcc=riscv
```

4. Build the target of your board...:

Go to litex-boards/litex_boards/targets and execute the target you want to build.

5. ... and/or install [Verilator](http://www.veripool.org/) and test LiteX directly on your computer without any FPGA board:

On Linux (Ubuntu):
```sh
$ sudo apt install libevent-dev libjson-c-dev verilator
$ litex_sim --cpu-type=vexriscv
```

On MacOS:
```sh
$ brew install json-c verilator libevent
$ brew cask install tuntap
$ litex_sim --cpu-type=vexriscv
```

6. Run a terminal program on the board's serial port at 115200 8-N-1.

  You should get the BIOS prompt like the one below.

<p align="center"><img src="https://raw.githubusercontent.com/enjoy-digital/litex/master/doc/bios_screenshot.png"></p>

# Community

<p align="center"><img src="https://raw.githubusercontent.com/enjoy-digital/litex/master/doc/litex-hub.png" width="400"></p>

Over the years a friendly community has grown around LiteX and the ecosystem of cores. Feedbacks and contributions have already greatly improved the project, EnjoyDigital still leads the development but it is now a community project and collaborative projects created around/with LiteX can be found at https://github.com/litex-hub.

# Contact
E-mail: florent@enjoy-digital.fr
