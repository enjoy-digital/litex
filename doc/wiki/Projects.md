# LiteX industrial projects

LiteX is developed and used by Enjoy-Digital since 2012 to co-develop full-systems with our partners and provide an convenient and efficient solutions to create SoCs on FPGA based systems. Here are some of the last project we worked on with our partners:

## PCIe Software Defined Radio board with 2 Artix7, PCIe Gen2 X8 and 2 AD937X. 
<div>
<img src="http://enjoy-digital.fr/experience/pcie_ad937x.jpg" width="520">
<img src="https://pbs.twimg.com/media/EjtsRYtX0AE72A1?format=jpg&name=medium" width="250">
</div>

The SoC is built with LiteX, [LitePCIe](https://github.com/enjoy-digital/litepcie) is used for the communication with the Host and [LiteJESD204B](https://github.com/enjoy-digital/litejesd204b) is used between the AD937Xs and FPGAs. 

## PCIe 3G SDI board with Artix7, PCIe Gen2 X4. 
<p align="center"><img src="http://enjoy-digital.fr/experience/pcie_3g_sdi.jpg" width="600"></p>

The SoC is built with LiteX, [LitePCIe](http://github.com/enjoy-digital/litepcie) is used to communicate with the Host and the Xilinx TripleRateSDI core is wrapped with custom datapath modules and gearboxes to make efficient use of the PCIe bus without any external buffering.

More projects can be found at [Enjoy-Digital website](http://enjoy-digital.fr/).

Even if these projects are still unfortunately proprietary, LiteX has been originally developed to create these systems and most of the open-source features/cores come directly from these projects. Working on these systems allow us to keep track of the industry standards/constraints, force us to be practical, use efficient solutions and motivate us to continue improving the tools/adding new features, because that's what we like: creating systems!

# LiteX open-source projects

Collections of projects with LiteX involved that could be useful for users to better understand LiteX, go further and/or find some inspiration.

## [LiteX-Acorn-Baseboard](https://github.com/enjoy-digital/litex-acorn-baseboard)

The LiteX-Acorn-Baseboards are baseboards developed around the SQRL's Acorn board (or Nite/LiteFury) expanding their possibilities.
<div>
<img src="https://raw.githubusercontent.com/enjoy-digital/litex-acorn-baseboard/master/hardware/acorn-baseboard-mini-proto.jpg" width="600">
</div>

## [Linux-on-LiteX-VexRiscv](https://github.com/litex-hub/linux-on-litex-vexriscv)
<div>
<img src="https://linuxgizmos.com/files/gsd_orangecrab_frontback.jpg" width="300">
<img src="https://web.archive.org/web/20200113121328im_/https://pbs.twimg.com/media/ENtF6OWXUAEwlA7.jpg" width="450">
</div>
 
 - Have an FPGA board with 32MB of RAM and want to test Linux on it? 
 - Want to study/explore a RISC-V Linux capable SoC?
 - Want to create a full autonomous SoC with LiteX and its peripherals (SPI, I2C, SDCard, FrameBuffer, etc...) managed by Linux?

[Linux-on-LiteX-VexRiscv](https://github.com/litex-hub/linux-on-litex-vexriscv) project demonstrates how to create a Linux capable SoC with [VexRiscv](https://github.com/SpinalHDL/VexRiscv) CPU, a 32-bits Linux Capable RISC-V CPU written in Spinal HDL. A SoC around the VexRiscv CPU is created using LiteX as the SoC builder and LiteX's cores written in Migen Python DSL (LiteDRAM, LiteEth, LiteSDCard). All the components used to create the SoC are open-source and the flexibility of Spinal HDL/Migen allow targeting easily very various FPGA devices/boards: Lattice, Altera, Xilinx, Microsemi FPGAs with SDRAM/DDR/DDR2/DDR3/DDR4 RAMs, RMII/MII/RGMII/1000BASE-X Ethernet PHYs. On Lattice ECP5 FPGAs, the [open source toolchain](https://github.com/SymbiFlow/prjtrellis) allows creating full open-source SoC with open-source cores **and** toolchain!

This project demonstrates **how high level HDLs (Spinal HDL, Migen) enable new possibilities and complement each other**. Results shown there are the results of a productive collaboration between open-source communities.ant to test easily control LiteX cores.

## [NeTV2](https://www.crowdsupply.com/alphamax/netv2)
<div>
<img src="https://bunniefoo.com/netv2/netv2-slogan-white.png" width="480">
<img src="http://enjoy-digital.fr/experience/netv2.jpg" width="400">
</div>

The NeTV2 is a HDMI capture/playback board based on an Xilinx Artix7 FPGA.

The [official SoC](https://github.com/AlphamaxMedia/netv2-fpga) is doing an overlay (up to 1080p60) from the Raspberry Pi 3B+ on an HDMI stream with or without HDCP. The SoC of the Artix7 FPGA is built with LiteX, a VexRiscv CPU is used for the control, [LiteDRAM](https://github.com/enjoy-digital/litedram) as the DDR3 controller to store the CPU firmware and the do HDMI buffering and [LiteVideo](https://github.com/enjoy-digital/litevideo) for the HDMI playback/capture.

The [libre SoC](https://github.com/enjoy-digital/netv2) makes use of the PCIe Gen2 X4 connector of the board with [LitePCIe](https://github.com/enjoy-digital/litepcie) to create a HDMI capture/playback device.

## [Fomu](https://www.crowdsupply.com/sutajio-kosagi/fomu)
<img src="https://web.archive.org/web/20211212031954im_/https://www.crowdsupply.com/img/9023/updated-fomu-penny_png_project-body.jpg" width="600">

The [Fomu](https://www.crowdsupply.com/sutajio-kosagi/fomu) is a tiny FPGA board that fits in your USB port. The SoC of the FPGA is built with LiteX,  a custom version of [VexRiscv](https://github.com/SpinalHDL/VexRiscv) CPU is used for the control and the [ValentyUSB](https://github.com/im-tomu/valentyusb) core allows the board to communicate with the Host computer and emulate various USB devices. Fomu demonstrates how iCE40 designs can be **tiny** and **powerful**: Fomu can run Micropython/Zephyr on its RISC-V CPU while allowing **software debug** over GDB and **gateware debug** over the USB bridge and is able to **reprogram itself** directly from USB with [Foboot](https://github.com/im-tomu/foboot). The [Fomu Workshop](https://workshop.fomu.im/en/latest/) workshop is also a great introduction to FPGA design.

## [A Trustworthy, Libre, Self-Hosting 64bit RISC-V Linux Computer](http://www.contrib.andrew.cmu.edu/~somlo/BTCP/)

Adding the [Rocket Chip](https://github.com/chipsalliance/rocket-chip) (64-bit RISC-V CPU) to the LiteX ecosystem, this project is capable of booting a *nearly* unmodified 64-bit upstream Linux kernel (with only the LiteEth network driver currently patched in).

Targeted toward the [ECP5-5G-Versa](https://www.latticesemi.com/en/Products/DevelopmentBoardsAndKits/ECP55GVersaDevKit) and the [TrellisBoard](https://github.com/daveshah1/TrellisBoard) (but also known to work on the [Nexys 4 DDR](https://store.digilentinc.com/nexys-a7-fpga-trainer-board-recommended-for-ece-curriculum/)), the ultimate goal is to boot a Linux distro (e.g., [Fedora](https://fedoraproject.org/wiki/Architectures/RISC-V)), and use native riscv64 builds of the Libre FPGA toolchain ([yosys](https://github.com/YosysHQ/yosys)/[trellis](https://github.com/SymbiFlow/prjtrellis)/[nextpnr](https://github.com/YosysHQ/nextpnr)) to build the underlying FPGA-based computer's **_own_** bitstream!

For the latest details, check out [http://www.contrib.andrew.cmu.edu/~somlo/BTCP](http://www.contrib.andrew.cmu.edu/~somlo/BTCP).

## [Betrusted.io](https://betrusted.io/)
<img src="https://betrusted.io/assets/images/betrusted-banner.png" width="600">

Betrusted is a protected place for your private matters. It’s built from the ground up to be checked by anyone, but sealed only by you. Betrusted is more than just a secure CPU – it is a system complete with screen and keyboard, because privacy begins and ends with the user.

Betrusted prototypes are built around two FPGAs SoC built with LiteX: The iCE40 based [Embedded controller](https://github.com/betrusted-io/betrusted-ec) SoC and the Spartan7 based [Secure Domain](https://github.com/betrusted-io/betrusted-soc) SoC.

<div>
<img src="https://bunniefoo.com/precursor/precursor_lte_module_example.jpg" width="400">
<img src="https://user-images.githubusercontent.com/1450143/98281974-cf1c5880-1f9d-11eb-8e5a-277723d6f1c9.png" width="400">
</div>

## [USB3 PIPE](https://github.com/enjoy-digital/usb3_pipe)
<img src="https://raw.githubusercontent.com/enjoy-digital/usb3_pipe/master/doc/breakout_board.jpg" width="600">

Current solutions for USB3 connectivity with an FPGA require the use of an external SerDes chip ([TI TUSB1310A - SuperSpeed 5 Gbps USB 3.0 Transceiver with PIPE and ULPI Interfaces](http://www.ti.com/product/TUSB1310A)) or external FIFO chip ([FTDI FT60X](https://www.ftdichip.com/Products/ICs/FT600.html) or Cypress [FX3](https://www.cypress.com/products/ez-usb-fx3-superspeed-usb-30-peripheral-controller)). The aim of this project is to experiment with [High Speed Transceivers (SERDES)](https://en.wikipedia.org/wiki/Multi-gigabit_transceiver) of popular FPGAs to create a [USB3.0 PIPE interface](https://www.intel.com/content/dam/www/public/us/en/documents/white-papers/phy-interface-pci-express-sata-usb30-architectures-3.1.pdf) and see if it's possible to just use the transceivers of the FPGA for the USB3 connectivity and have the USB3 PIPE directly implemented in the fabric (and then avoid any external chip!)

## [PCIe Analyzer](https://github.com/enjoy-digital/pcie_analyzer)
<img src="https://github.com/enjoy-digital/pcie_analyzer/raw/master/doc/banner.jpg" width="600">

The aim of this project is to create a PCIe interposer + FPGA capture board for PCIe signals capture and analysis with cheap hardware.

## [Chubby75](https://github.com/q3k/chubby75)
<img src="https://github.com/q3k/chubby75/raw/master/5a-75b/images/cl-5a-75b-v61-front-annotated.jpg" width="600">

Chubby75 project documents cheap FPGA based led controllers (15$ shipping included) that can be repurposed as FPGA development boards with 2x 1Gbps interfaces / Spartan6 or ECP5 FPGAs / SDRAM, be used as GPIOs over network devices or for their original purpose: control led panels for a [led cube](https://github.com/NiklasFauth/colorlight-led-cube) :) LiteX and [LiteEth](https://github.com/enjoy-digital/liteeth) have been tested on the reversed pinout and boards are supported in [LiteX-boards](https://github.com/litex-hub/litex-boards).
