# LiteX Tutorials

## [FPGA 101](https://github.com/litex-hub/fpga_101)
Lessons/Labs given to students to discover FPGAs and learn Migen/LiteX through a hands-on approach.  These tutorials are covering the Migen's basics (syntax/simulations) through common SoC cores: Clock generation, 7-Segments displays, etc... and then the LiteX's basics through the integration of these cores in a SoC. It demonstrates and explains how to control these cores from an Host PC through a bridge (UART) and then directly from a RISC-V Soft-CPU implemented in the FPGA.

These tutorials should help users understand the possibilities of Migen/LiteX and give the basics to create their own Migen cores/LiteX SoCs.

> **Note:** The labs are based on the Nexys4DDR (now named NexysA7) but can be easily adapted to others boards. Since these tutorials have been written, new less expensive open-source FPGA boards, also compatible with open-source FPGA toolchains, are widely available. The tutorials will probably be adapted to support such boards in the future.

## [fjullien's training](https://github.com/fjullien/migen_litex_tutorials)
A series of tutorials by fjullien focused on teaching Migen and LiteX. These hands-on labs help users understand FPGA design, SoC integration, and the creation of custom cores using Migen, alongside building complete systems with LiteX.

## [Fomu Workshop](https://workshop.fomu.im/en/latest/)
![Fomu FPGA board](https://web.archive.org/web/20211212031953im_/https://www.crowdsupply.com/img/decb/fomu-front-back-03_png_project-body.jpg)

The [Fomu](https://www.crowdsupply.com/sutajio-kosagi/fomu) is a tiny FPGA board that fits in your USB port. The SoC of the FPGA is built with LiteX and the workshop provides a hands-on approach to control the peripherals from a Host PC through the USB bridge from the [ValentyUSB](https://github.com/im-tomu/valentyusb) core and then demonstrates how to create a RISC-V SoC with a [VexRiscv](https://github.com/SpinalHDL/VexRiscv) CPU and load/execute/debug C/Rust core with it and control the peripherals of the board.

## [360nosc0pe LiteX SoC](https://github.com/360nosc0pe/scope)
![](https://user-images.githubusercontent.com/1450143/120784644-9856f280-c52c-11eb-8d99-1ec916dea836.png)

LiteX based FPGA SoC designed for the Siglent SDS1104X-E oscilloscope, providing an open-source implementation to enhance and extend the scope's functionality.

## [Thunderscope LiteX SoC](https://github.com/enjoy-digital/thunderscope)
![](https://user-images.githubusercontent.com/1450143/179495534-4c54973b-9203-4893-9eaa-d9177413e9bf.png)

LiteX based FPGA SoC for the ThunderScope Scope.

## [ColorLite](https://github.com/enjoy-digital/colorlite)
![](https://raw.githubusercontent.com/enjoy-digital/colorlite/master/doc/power_off.jpg)

The Colorlight 5A-75B is an inexpensive (15$) led control board equipped with a Lattice ECP5 FPGA, 2 x 1Gbps Ethernet and lots of IOs. ColorLite project explains how to create a cheap remote control/monitoring system with it can be useful to discover LiteX/LiteEth through a practical example.

## [iCEBreaker LiteX examples](https://github.com/icebreaker-fpga/icebreaker-litex-examples)
![enter image description here](https://web.archive.org/web/20230321080334im_/https://www.crowdsupply.com/img/301a/icebreaker-iso_png_project-body.jpg)

The [iCEBreaker](https://www.crowdsupply.com/1bitsquared/icebreaker-fpga) is the first open source iCE40 FPGA development board designed for teachers and students. The iCEBreaker [target](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/targets/icebreaker.py) integrated in [LiteX-Boards](https://github.com/litex-hub/litex-boards) provides a minimal LiteX SoC for the iCEBreaker with a CPU, its ROM (in SPI Flash), its SRAM, close to the others LiteX targets. A more complete example of LiteX SoC for the iCEBreaker with more features, examples to run C/Rust code on the RISC-V CPU and documentation can be found in the [iCEBreaker LiteX examples](https://github.com/icebreaker-fpga/icebreaker-litex-examples) tutorial.

# Useful resources

## [LiteX for Hardware Engineers](LiteX-for-Hardware-Engineers.md) 
Blogpost/Wiki by @bunnie from 2018 with his understanding of LiteX and tips for engineers with a hardware background.

## [LiteX BuildEnv Wiki](https://github.com/timvideos/litex-buildenv/wiki)
Wiki of LiteX Buildenv project with information complementary to LiteX's Wiki.

## [LiteX SoftCPU on the ULX3S](https://gojimmypi.blogspot.com/2020/03/litex-soft-cpu-on-ulx3s-reloading.html) 
Blogpost by gojimmypi testing LiteX on the ULX3S board and experimenting with the Soft CPU.

## [Colorlight i5 Tips](https://github.com/kazkojima/colorlight-i5-tips) 
Tiny collection of tips for the [Colorlight i5 FPGA board](https://github.com/wuxx/Colorlight-FPGA-Projects).

## [SQRL Acorn / LitePCIe / Thunderbolt](https://github.com/SMB784/SQRL_quickstart) 
Use of the SQRL Acorn with LitePCIe in a Thunderbolt/nVME enclosure.

## [FemtoRV CPU with LiteX on ULX3S](https://github.com/BrunoLevy/learn-fpga/tree/master/LiteX)
Discovery/Use of LiteX with FemtoRV CPU by @BrunoLevy.

## [Building a SoC in an FPGA in less than (literally) 5 minutes?](https://www.controlpaths.com/2022/01/17/building-soc-litex/)
Discovery of LiteX as a SoC Builder by @controlpaths

## [Running Linux with LiteX and VexRiscv on Arty A7](https://jia-je.translate.goog/hardware/2023/04/19/litex-digilent-arty-a7/?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=fr&_x_tr_pto=wapp)

## [DRAM topology and training](https://jia-je.translate.goog/hardware/2023/04/20/dram-topology-training/?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=fr&_x_tr_pto=wapp)

## [Librecar](http://saketsinha.de/librecar-wiki/title-page.html)
Librecar is an automotive exploration tool focused on vehicle protocol emulation and data handling, using low-cost FPGA to manage CANbus.

## [Linux on Tang Primer](https://www.luffca.com/2022/10/linux-tang-primer/)
A project running dual-core 32-bit RISC-V Linux on the affordable Sipeed Tang Primer FPGA board, describing changes done to Linux-on-LiteX-VexRiscv project.​

