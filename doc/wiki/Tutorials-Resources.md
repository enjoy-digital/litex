# Tutorials and resources

Where to learn Migen and LiteX, examples to read, and what has been written and said about
LiteX. The wiki itself: start with [Installation](Installation.md), [Create a minimal SoC](Create-A-minimal-SoC.md)
and [The LiteX approach](LiteX-Approach.md).

## Tutorials and workshops

### [FPGA 101](https://github.com/litex-hub/fpga_101)
Lessons/Labs given to students to discover FPGAs and learn Migen/LiteX through a hands-on approach. These tutorials are covering the Migen's basics (syntax/simulations) through common SoC cores: Clock generation, 7-Segments displays, etc... and then the LiteX's basics through the integration of these cores in a SoC. It demonstrates and explains how to control these cores from an Host PC through a bridge (UART) and then directly from a RISC-V Soft-CPU implemented in the FPGA.

These tutorials should help users understand the possibilities of Migen/LiteX and give the basics to create their own Migen cores/LiteX SoCs.

> **Note:** The labs are based on the Nexys4DDR (now named NexysA7) but can be easily adapted to others boards; the inexpensive boards of [LiteX-Boards](https://github.com/litex-hub/litex-boards) that work with the open-source toolchains are good candidates.

### [fjullien's training](https://github.com/fjullien/migen_litex_tutorials)
A series of tutorials by fjullien focused on teaching Migen and LiteX. These hands-on labs help users understand FPGA design, SoC integration, and the creation of custom cores using Migen, alongside building complete systems with LiteX.

### [Fomu Workshop](https://workshop.fomu.im/en/latest/)
The [Fomu](https://www.crowdsupply.com/sutajio-kosagi/fomu) is a tiny FPGA board that fits in your USB port. The SoC of the FPGA is built with LiteX and the workshop provides a hands-on approach to control the peripherals from a Host PC through the USB bridge from the [ValentyUSB](https://github.com/im-tomu/valentyusb) core and then demonstrates how to create a RISC-V SoC with a [VexRiscv](https://github.com/SpinalHDL/VexRiscv) CPU and load/execute/debug C/Rust core with it and control the peripherals of the board.

### [iCEBreaker LiteX examples](https://github.com/icebreaker-fpga/icebreaker-litex-examples)
The [iCEBreaker](https://www.crowdsupply.com/1bitsquared/icebreaker-fpga) is the first open source iCE40 FPGA development board designed for teachers and students. The iCEBreaker [target](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/targets/icebreaker.py) integrated in [LiteX-Boards](https://github.com/litex-hub/litex-boards) provides a minimal LiteX SoC for the iCEBreaker with a CPU, its ROM (in SPI Flash), its SRAM, close to the others LiteX targets. A more complete example of LiteX SoC for the iCEBreaker with more features, examples to run C/Rust code on the RISC-V CPU and documentation can be found in the [iCEBreaker LiteX examples](https://github.com/icebreaker-fpga/icebreaker-litex-examples) tutorial.

### [LiteX for Hardware Engineers](LiteX-for-Hardware-Engineers.md)
An introduction to LiteX written in 2018 by [bunnie](https://www.bunniestudios.com/) for engineers with a Verilog/Vivado background, with his tips; kept in this wiki with notes on what changed since.

### [Migen manual](https://m-labs.hk/migen/manual)
The language LiteX and its cores are written in: `Module`, `Signal`, `If`/`Case`, `FSM`, `Record`, the specials and the simulator.

## Examples to read

### [LiteX-Boards targets](https://github.com/litex-hub/litex-boards/tree/master/litex_boards/targets)
250+ reference SoCs: the shortest way to see how a DRAM, an Ethernet PHY, a flash or a video output is added on a board like yours.

### [ColorLite](https://github.com/enjoy-digital/colorlite)
![](https://raw.githubusercontent.com/enjoy-digital/colorlite/master/doc/power_off.jpg)

The Colorlight 5A-75B is an inexpensive (15$) led control board equipped with a Lattice ECP5 FPGA, 2 x 1Gbps Ethernet and lots of IOs. ColorLite project explains how to create a cheap remote control/monitoring system with it: discover LiteX/LiteEth and the host bridges through a practical example.

### [360nosc0pe LiteX SoC](https://github.com/360nosc0pe/scope)
![](https://user-images.githubusercontent.com/1450143/120784644-9856f280-c52c-11eb-8d99-1ec916dea836.png)

LiteX based FPGA SoC designed for the Siglent SDS1104X-E oscilloscope, providing an open-source implementation to enhance and extend the scope's functionality: a complete instrument (ADC frontend, DRAM capture, Ethernet, Linux) in one target.

### [ThunderScope LiteX SoC](https://github.com/EEVengers/thunderscope_litex)
![](https://user-images.githubusercontent.com/1450143/179495534-4c54973b-9203-4893-9eaa-d9177413e9bf.png)

LiteX based FPGA SoC for the ThunderScope oscilloscope: ADC capture, LiteDRAM and LitePCIe DMAs to the host.

### [USB3-PIPE](https://github.com/enjoy-digital/usb3_pipe), [TriXium](https://github.com/enjoy-digital/trixium), [LiteX-M2SDR](https://github.com/enjoy-digital/litex_m2sdr)
Recent Enjoy-Digital projects documented end to end (architecture diagrams, simulation, measurements, method): how a large LiteX design is organized and validated. More on the [Projects](Projects.md) page.

### [litex-template](https://github.com/sergachev/litex-template)
A template for a LiteX project outside LiteX-Boards, with the Zynq and ZynqMP workflows.

## Articles and blog posts

- [LiteX Notes](https://enjoy-digital.github.io/), the Enjoy-Digital blog, "notes from building FPGA SoCs with LiteX":
  [CamLink 4K: open gateware and firmware for the Elgato Cam Link 4K](https://enjoy-digital.github.io/posts/camlink-4k/),
  [ChromatiX: the Chromatic bitstream, rebuilt with LiteX](https://enjoy-digital.github.io/posts/chromatix/),
  [Doom on ChromatiX: from 4 to 31 fps in a day](https://enjoy-digital.github.io/posts/chromatix-doom/),
  [ChromatiX SDR: a spectrum analyzer from the Chromatic's ESP32](https://enjoy-digital.github.io/posts/chromatix-sdr/),
  [LiteSATA on ECP5: SATA for the fully open FPGA flow](https://enjoy-digital.github.io/posts/litesata-ecp5/) (2026).
- [LiteX vs. Vivado: First Impressions](https://www.bunniestudios.com/blog/?p=5018), bunnie (2018).
- [Building a SoC in an FPGA in less than (literally) 5 minutes?](https://www.controlpaths.com/2022/01/17/building-soc-litex/), controlpaths (2022).
- [Running Linux with LiteX and VexRiscv on Arty A7](https://jia-je.translate.goog/hardware/2023/04/19/litex-digilent-arty-a7/?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=fr&_x_tr_pto=wapp) and [DRAM topology and training](https://jia-je.translate.goog/hardware/2023/04/20/dram-topology-training/?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=fr&_x_tr_pto=wapp), Jiajie Chen (2023).
- [Linux on Tang Primer](https://www.luffca.com/2022/10/linux-tang-primer/): dual-core 32-bit RISC-V Linux on the Sipeed Tang Primer, with the changes made to Linux-on-LiteX-VexRiscv (2022).
- [LiteX SoftCPU on the ULX3S](https://gojimmypi.blogspot.com/2020/03/litex-soft-cpu-on-ulx3s-reloading.html), gojimmypi (2020).
- [FemtoRV CPU with LiteX on ULX3S](https://github.com/BrunoLevy/learn-fpga/tree/master/LiteX), Bruno Levy's learn-fpga.
- [SQRL Acorn / LitePCIe / Thunderbolt](https://github.com/SMB784/SQRL_quickstart): the Acorn with LitePCIe in a Thunderbolt NVMe enclosure.
- [Colorlight i5 tips](https://github.com/kazkojima/colorlight-i5-tips), [Librecar](http://saketsinha.de/librecar-wiki/title-page.html) (CAN bus exploration on low-cost FPGAs).
- [LiteX BuildEnv wiki](https://github.com/timvideos/litex-buildenv/wiki) (TimVideos, legacy but still informative on Linux/Zephyr/MicroPython flows).
- [DeepWiki: LiteX](https://deepwiki.com/enjoy-digital/litex): an AI-generated, searchable walkthrough of the LiteX repository ([for agents](LiteX-for-AI-Agents.md)).

## Talks and papers

- [LiteX: an open-source SoC builder and library based on Migen Python DSL](https://osda.gitlab.io/19/1.1.pdf) ([slides](https://osda.gitlab.io/19/1.1-slides.pdf)), OSDA 2019 workshop at DATE.
- [LiteX SoC builder framework quick tour](https://docs.google.com/presentation/d/1mQOWqgmyQxpjLAzFwCulqgkp0TuxmaIDYp5iUfPqqIk/edit?usp=sharing), slides.
- [Snakes and Rabbits: how CCC shaped an open hardware success](https://www.youtube.com/watch?v=AlmVxR0417c), 35C3 (2018).
- [Tim has too many projects, Latch-Up edition](https://www.youtube.com/watch?v=v7WrTmexod0), Tim Ansell (2019).
- [LiteX framework for FPGA+Embedded codesign through hands-on examples](https://cfp.balccon.org/balccon2k25-2025/talk/RUP3RD/), Tarik Hamedovic, BalCCon2k25 (2025).
- [Self-hosting Fedora on a LiteX + Rocket FPGA computer](https://www.contrib.andrew.cmu.edu/~somlo/BTCP/self_hosting_fedora.html), Gabriel Somlo, FOSDEM 2023.

Something missing? [Add it](Contributing-to-the-Wiki.md).
