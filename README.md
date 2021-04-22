<p align="center"><img src="https://raw.githubusercontent.com/enjoy-digital/litex/master/doc/litex.png"></p>

```
                          Copyright 2012-2021 / Enjoy-Digital
```
[![](https://github.com/enjoy-digital/litex/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litex/actions)
![License](https://img.shields.io/badge/License-BSD%202--Clause-orange.svg)

# Welcome to LiteX!

LiteX is a Migen/MiSoC based Core/SoC builder that provides the infrastructure to easily create Cores/SoCs (with or without CPU).
The common components of a SoC are provided directly: Buses and Streams (Wishbone, AXI, Avalon-ST), Interconnect, Common cores (RAM, ROM, Timer, UART, etc...), CPU wrappers/integration, etc... and SoC creation capabilities can be greatly extended with the ecosystem of LiteX cores (DRAM, PCIe, Ethernet, SATA, etc...) that can be integrated/simulated/build easily with LiteX. It also provides build backends for open-source and vendors toolchains.

Think of Migen as a toolbox to create FPGA designs in Python and LiteX as a
SoC builder to create/develop/debug FPGA SoCs in Python.

**Want to get started and/or looking for documentation? Make sure to visit the [Wiki](https://github.com/enjoy-digital/litex/wiki)!**

**A question or want to get in touch? Our IRC channel is [#litex at freenode.net](https://webchat.freenode.net/?channels=litex)**

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
| [LiteVideo](http://github.com/enjoy-digital/litevideo)       | [![](https://github.com/enjoy-digital/litevideo/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litevideo/actions)       | VGA, DVI, HDMI            |
| [LiteScope](http://github.com/enjoy-digital/litescope)       | [![](https://github.com/enjoy-digital/litescope/workflows/ci/badge.svg)](https://github.com/enjoy-digital/litescope/actions)       | Logic analyzer            |

By combining LiteX with the ecosystem of cores, creating complex SoCs becomes easier than with traditional tools while providing better portability and flexibility. Here are some projects created recently with the tools:

A Multi-core Linux Capable SoC based on VexRiscv-SMP CPU, LiteDRAM, LiteSATA and integrated with LiteX:
![](https://user-images.githubusercontent.com/1450143/103343266-f8cc9a00-4a8b-11eb-9444-f02e1522a490.png)For more info, have a look at [Linux-on-LiteX-Vexriscv](https://github.com/litex-hub/linux-on-litex-vexriscv) project and try running Linux on your FPGA board!

A custom PCIe SDI Capture/Playback board built around LitePCIe and integrated with LiteX, allowing full control of the SDI flow and very low latency.
![](https://user-images.githubusercontent.com/1450143/103343791-282fd680-4a8d-11eb-82bd-c068ac1ad293.png)
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
$ ./litex_setup.py init install --user (--user to install to user directory)
```
  Later, if you need to update all repositories:
```sh
$ ./litex_setup.py update
```

> **Note:** On MacOS, make sure you have [HomeBrew](https://brew.sh) installed. Then do, ``brew install wget``.

> **Note:** On Windows, it's possible you'll have to set `SHELL` environment variable to `SHELL=cmd.exe`.

3. Install a RISC-V toolchain (Only if you want to test/create a SoC with a CPU):
```sh
$ ./litex_setup.py gcc
```

4. Build the target of your board...:

Go to litex-boards/litex_boards/targets and execute the target you want to build.

5. ... and/or install [Verilator](http://www.veripool.org/) and test LiteX directly on your computer without any FPGA board:

On Linux (Ubuntu):
```sh
$ sudo apt install libevent-dev libjson-c-dev verilator
$ lxsim --cpu-type=vexriscv
```

On MacOS:
```sh
$ brew install json-c verilator libevent
$ brew cask install tuntap
$ lxsim --cpu-type=vexriscv
```

6. Run a terminal program on the board's serial port at 115200 8-N-1.

  You should get the BIOS prompt like the one below.

<p align="center"><img src="https://raw.githubusercontent.com/enjoy-digital/litex/master/doc/bios_screenshot.png"></p>

# Community

<p align="center"><img src="https://raw.githubusercontent.com/enjoy-digital/litex/master/doc/litex-hub.png" width="400"></p>

LiteX has been initially developed by EnjoyDigital to create custom SoCs/Systems for our clients
(and we are still using it for that purpose :)); but over the years a friendly community has grown
around LiteX and the ecosystem of cores. Feedbacks and contributions have already greatly improved
the project, EnjoyDigital still leads the development but it is now a community project and collaborative
projects created around/with LiteX can be found at https://github.com/litex-hub.

# Contact
E-mail: florent@enjoy-digital.fr
