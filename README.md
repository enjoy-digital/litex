![LiteX](https://raw.githubusercontent.com/enjoy-digital/litex/master/doc/litex.png)
```
              Copyright 2012-2019 / EnjoyDigital
```
[![](https://travis-ci.com/enjoy-digital/litex.svg?branch=master)](https://travis-ci.com/enjoy-digital/litex)
![License](https://img.shields.io/badge/License-BSD%202--Clause-orange.svg)
# Welcome to LiteX!
LiteX is a FPGA design/SoC builder that can be used to build cores, create
SoCs and full FPGA designs.

LiteX is based on Migen and provides specific building/debugging tools for
a higher level of abstraction and compatibily with the LiteX core ecosystem.

Think of Migen as a toolbox to create FPGA designs in Python and LiteX as a
SoC builder to create/develop/debug FPGA SoCs in Python.

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
LiteX already supports various softcores CPUs: LM32, Mor1kx, PicoRV32, VexRiscv
and is compatible with the LiteX's Cores Ecosystem:

| Name                                                         | Build Status                                                            | Description                   |
| ------------------------------------------------------------ | ----------------------------------------------------------------------- | ----------------------------- |
| [LiteDRAM](http://github.com/enjoy-digital/litedram)         | [![](https://travis-ci.org/enjoy-digital/litedram.svg?branch=master)](https://travis-ci.org/enjoy-digital/litedram)     | DRAM        |
| [LiteEth](http://github.com/enjoy-digital/liteeth)           | [![](https://travis-ci.com/enjoy-digital/liteeth.svg?branch=master)](https://travis-ci.com/enjoy-digital/liteeth)       | Ethernet                      |
| [LitePCIe](http://github.com/enjoy-digital/litepcie)         | [![](https://travis-ci.com/enjoy-digital/litepcie.svg?branch=master)](https://travis-ci.com/enjoy-digital/litepcie)     | PCIe                          |
| [LiteSATA](http://github.com/enjoy-digital/litesata)         | [![](https://travis-ci.com/enjoy-digital/litesata.svg?branch=master)](https://travis-ci.com/enjoy-digital/litesata)     | SATA                          |
| [LiteSDCard](http://github.com/enjoy-digital/litesdcard)     | [![](https://travis-ci.com/enjoy-digital/litesdcard.svg?branch=master)](https://travis-ci.com/enjoy-digital/litesdcard)   | SD card                       |
| [LiteICLink](http://github.com/enjoy-digital/liteiclink)     | [![](https://travis-ci.com/enjoy-digital/liteiclink.svg?branch=master)](https://travis-ci.com/enjoy-digital/liteiclink)   | Inter-Chip communication      |
| [LiteJESD204B](http://github.com/enjoy-digital/litejesd204b) | [![](https://travis-ci.com/enjoy-digital/litejesd204b.svg?branch=master)](https://travis-ci.com/enjoy-digital/litejesd204b) | JESD204B                      |
| [LiteVideo](http://github.com/enjoy-digital/litevideo)       | [![](https://travis-ci.com/enjoy-digital/litevideo.svg?branch=master)](https://travis-ci.com/enjoy-digital/litevideo)    | VGA, DVI, HDMI                     |
| [LiteScope](http://github.com/enjoy-digital/litescope)       | [![](https://travis-ci.com/enjoy-digital/litescope.svg?branch=master)](https://travis-ci.com/enjoy-digital/litescope)    | Logic analyzer  |

# Sub-packages
**litex.gen**
Provides specific or experimental modules to generate HDL that are not integrated in Migen.

**litex.build:**
Provides tools to build FPGA bitstreams (interface to vendor toolchains) and to simulate HDL code or full SoCs.

**litex.soc:**
Provides definitions/modules to build cores (bus, bank, flow), cores and tools to build a SoC from such cores.

**litex.boards:**
Provides platforms and targets for the supported boards. All Migen's platforms can also be used in LiteX. The boards present in the LiteX repository are the official ones that are used for development/CI. More boards are available at: https://github.com/litex-hub/litex-boards

# Papers, Presentations, Tutorials, Links
**FPGA lessons/tutorials:**
- https://github.com/enjoy-digital/fpga_101

**OSDA paper/slides:**
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

# Very Quick start guide (for newcomers)
TimVideos.us has done an awesome job for setting up a LiteX environment easily in the litex-buildenv repo: https://github.com/timvideos/litex-buildenv

It's recommended for newcomers to go this way. Various FPGA boards are supported and multiple examples provided! You can even run Linux on your FPGA using LiteX very easily!

Migen documentation can be found here: https://m-labs.hk/migen/manual

# Quick start guide (for advanced users)
0. Install Python 3.5+ and FPGA vendor's development tools.
1. Install Migen/LiteX and the LiteX's cores:
```sh
$ wget https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py
$ chmod +x litex_setup.py
$ ./litex_setup.py init install --user (--user to install to user directory)
```
  Later, if you need to update all repositories:
```sh
$ ./litex_setup.py update
```
3. Install a RISC-V toolchain:
```sh
$ wget https://static.dev.sifive.com/dev-tools/riscv64-unknown-elf-gcc-8.1.0-2019.01.0-x86_64-linux-ubuntu14.tar.gz
$ tar -xvf riscv64-unknown-elf-gcc-8.1.0-2019.01.0-x86_64-linux-ubuntu14.tar.gz
$ export PATH=$PATH:$PWD/riscv64-unknown-elf-gcc-8.1.0-2019.01.0-x86_64-linux-ubuntu14/bin/
```
4. Build the target of your board...:
  Go to litex-boards/litex_boards/xxyy/targets (xxyy being community/official/partner) and execute the target you want to build

5. ... and/or install Verilator and test LiteX on your computer:
  Download and install Verilator: http://www.veripool.org/
  On Fedora:
```sh
$ sudo dnf install libevent-devel json-c-devel
```
  On Ubuntu:
```sh
$ sudo apt install libevent-dev libjson-c-dev
$ litex_sim
```

6. Run a terminal program on the board's serial port at 115200 8-N-1.
  You should get the BIOS prompt.

# Contact
E-mail: florent@enjoy-digital.fr