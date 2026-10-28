LiteX has been used since 2012 by [Enjoy-Digital](https://enjoy-digital.fr) to build systems
for clients and open-source products, and by a growing community for boards, instruments,
research platforms and products of their own. This page lists them in four groups: the
**industrial projects** LiteX was born from and lives from, the **Enjoy-Digital projects**
(the framework, the cores and the systems we maintain), the **LiteX-Hub collaborative
projects** (the shared repositories of the community), and the **community projects** built
with LiteX elsewhere. Yours is missing? [Send a pull request](Contributing-to-the-Wiki.md) with a line
and a link.

## Industrial projects

LiteX was born in industrial projects and still lives from them: since 2012,
[Enjoy-Digital](https://enjoy-digital.fr) co-develops complete FPGA systems with its clients,
and this work funds the development of LiteX and of the cores. It also keeps us pragmatic: real
boards, industry standards and deadlines call for practical and efficient solutions, while
leaving room for the R&D we like (USB3 without external PHY, White Rabbit, PCIe PTM, LLMs
decoded on FPGA...). Here are some of the projects we worked on with our clients.

### White Rabbit PCIe NIC on the SPEC-A7, for the Warsaw University of Technology

[LiteX-WR-NIC](https://github.com/enjoy-digital/litex_wr_nic): a White Rabbit PCIe NIC
(sub-nanosecond synchronization over Ethernet) on the SPEC-A7 board: LiteX, LitePCIe with PTM,
LiteEth and the White Rabbit PTP core, with a PTM demonstration against an Intel I225. Open
source end to end.

<img src="https://raw.githubusercontent.com/enjoy-digital/litex_wr_nic/main/doc/spec_a7.jpg" width="500">

### PCIe Software Defined Radio board with 2 Artix7, PCIe Gen2 X8 and 2 AD937X
<div>
<img src="http://enjoy-digital.fr/experience/pcie_ad937x.jpg" width="520">
<img src="https://pbs.twimg.com/media/EjtsRYtX0AE72A1?format=jpg&name=medium" width="250">
</div>

The SoC is built with LiteX, [LitePCIe](https://github.com/enjoy-digital/litepcie) is used for the communication with the Host and [LiteJESD204](https://github.com/enjoy-digital/litejesd204) is used between the AD937Xs and FPGAs.

### PCIe 3G SDI board with Artix7, PCIe Gen2 X4
<p align="center"><img src="http://enjoy-digital.fr/experience/pcie_3g_sdi.jpg" width="600"></p>

The SoC is built with LiteX, [LitePCIe](http://github.com/enjoy-digital/litepcie) is used to communicate with the Host and the Xilinx TripleRateSDI core is wrapped with custom datapath modules and gearboxes to make efficient use of the PCIe bus without any external buffering.

More projects can be found on the [Enjoy-Digital website](https://enjoy-digital.fr/).

Most of these systems stay proprietary, but most of the open-source features and cores come
directly from them: when something developed for a client is generic enough (a core, a PHY, a
tool, a CPU integration), we look with the client at how to bring it back into the generic
projects. This is how LiteX, LitePCIe, LiteEth or LiteDRAM grew, and how the client gets a
feature maintained upstream rather than a fork. We love working on concrete problems and
systems: for custom developments or personalized support on LiteX, contact us at
[florent@enjoy-digital.fr](mailto:florent@enjoy-digital.fr).

## Enjoy-Digital projects

### The framework and the cores

[LiteX](https://github.com/enjoy-digital/litex) and the cores ecosystem:
[LiteDRAM](https://github.com/enjoy-digital/litedram), [LiteEth](https://github.com/enjoy-digital/liteeth),
[LitePCIe](https://github.com/enjoy-digital/litepcie), [LiteNVMe](https://github.com/enjoy-digital/litenvme),
[LiteSATA](https://github.com/enjoy-digital/litesata), [LiteSDCard](https://github.com/enjoy-digital/litesdcard),
[LiteICLink](https://github.com/enjoy-digital/liteiclink), [LiteJESD204](https://github.com/enjoy-digital/litejesd204),
[LiteScope](https://github.com/enjoy-digital/litescope), [LiteDSP](https://github.com/enjoy-digital/litedsp)
and [USB3-PIPE / usb3_core](https://github.com/enjoy-digital/usb3_pipe): see the [Cores ecosystem](Cores-Ecosystem.md).
Software ports: [FreeRTOS on LiteX](https://github.com/enjoy-digital/freertos-on-litex),
[MQuickJS on LiteX](https://github.com/enjoy-digital/mquickjs-on-litex). Infrastructure:
[LiteX hardware CI](https://github.com/enjoy-digital/litex_hw_ci) (the designs run on real
boards).

### Systems and products

**[TriXium](https://github.com/enjoy-digital/trixium)**: ternary LLMs (PrismML's Bonsai models,
1.7B to 27B parameters) decoded entirely on second-hand FPGA cards (Kintex-7, Virtex
UltraScale+ with DDR4 or HBM2, Efinix Ti375), open source end to end: LiteX, LitePCIe,
LiteDRAM, VexiiRiscv provide the SoC and the memory controllers, the inference core and
firmware were developed with an AI agent guided by Enjoy-Digital. Documented with the
simulation-first method and the LiteX-style diagrams this wiki now uses.

<img src="https://raw.githubusercontent.com/enjoy-digital/trixium/main/doc/images/trixium-project.png" width="700">

**[LiteX-M2SDR](https://github.com/enjoy-digital/litex_m2sdr)**: an M.2 software defined radio
board (Artix-7, AD9361 2T2R up to 61.44 MSPS, PCIe Gen2 x1/x2/x4 with PTM, SATA, Ethernet
and White Rabbit options) with its LitePCIe-based driver, tools, SoapySDR module and GNU Radio
support; used with srsRAN, Amarisoft and research projects.

<img src="https://github.com/user-attachments/assets/c3007b14-0c55-4863-89fa-749082692b4f" width="700">

**[USB3-PIPE and usb3_core](https://github.com/enjoy-digital/usb3_pipe)**: USB 3.0 SuperSpeed
for FPGAs without any external chip: the PIPE PHY (LTSSM, 8b/10b, scrambling) on the FPGA
transceivers and a complete USB3 device core (link/protocol layers, endpoints, CDC-ACM, UVC
camera, mass storage, composite devices), 446 MB/s bulk, also exported as a standalone core;
[AgentLab](https://github.com/enjoy-digital/usb3_pipe/blob/master/doc/agentlab.md), a USB3
instrument giving software agents consoles, GPIOs, a logic analyzer and JTAG on a device under
test, is built on it.

<img src="https://raw.githubusercontent.com/enjoy-digital/usb3_pipe/master/doc/acorn_baseboard_sfp2usb_0.jpg" width="700">

**[LiteX Acorn Baseboard](https://github.com/enjoy-digital/litex-acorn-baseboard)** (and
Mini): baseboards turning the SQRL Acorn (and NiteFury/LiteFury) mining cards into FPGA
development boards: serial, Ethernet, SFP cages, HDMI, SD card, SATA/USB3 through the M.2
connector; the development target of several projects here
([Use LiteX on the Acorn](Use-LiteX-on-the-Acorn-CLE-215.md)).

<img src="https://raw.githubusercontent.com/enjoy-digital/litex-acorn-baseboard/master/hardware/acorn-baseboard-mini-sqrl-acorn.jpg" width="600">

**[ChromatiX](https://github.com/enjoy-digital/chromatix)**: the ModRetro Chromatic's FPGA
design (a Game Boy-compatible handheld on a Gowin GW5A) freed and rebuilt with LiteX, with
the USB 2.0 soft PHY, Doom at 31 fps and a spectrum analyzer from the ESP32
([blog posts](https://enjoy-digital.github.io/)). **[CamLink 4K](https://github.com/enjoy-digital/camlink_4k)**:
the Elgato Cam Link 4K capture dongle (ECP5, FX3) rebuilt with open-source LiteX gateware and
bare-metal FX3 firmware.

<img src="https://raw.githubusercontent.com/enjoy-digital/chromatix/main/doc/images/chromatix.jpg" width="340"> <img src="https://raw.githubusercontent.com/enjoy-digital/camlink_4k/main/doc/images/camlink_4k-inside.jpg" width="340">

**[ThunderScope](https://github.com/EEVengers/thunderscope_litex)** (gateware for the
EEVengers Thunderbolt/PCIe oscilloscope, now maintained upstream by EEVengers),
**[XTRX](https://github.com/enjoy-digital/litex_xtrx)** and [xtrx_julia](https://github.com/enjoy-digital/xtrx_julia)
(an alternative LitePCIe gateware and software for the LimeSDR XTRX, with Julia Computing),
**[LimeSDR_GW](https://github.com/myriadrf/LimeSDR_GW)** (the LiteX gateware of the LimeSDR
Mini v2, XTRX and LimeSDR boards, with MyriadRF/Lime Microsystems),
**[PCIe Screamer](https://github.com/enjoy-digital/pcie_screamer)** and
**[PCIe Analyzer](https://github.com/enjoy-digital/pcie_analyzer)** (PCIe TLP experiments and
a PCIe interposer/capture board), **[ColorLite](https://github.com/enjoy-digital/colorlite)**
(a remote control/monitoring system on the 15$ Colorlight 5A-75B, a LiteEth tutorial),
**[NeTV2](https://www.crowdsupply.com/alphamax/netv2)** (the HDMI capture/overlay board of
bunnie: the [official SoC](https://github.com/AlphamaxMedia/netv2-fpga) is a LiteX SoC with
VexRiscv, LiteDRAM and LiteVideo), **[litecompute_sdr_poc](https://github.com/enjoy-digital/litecompute_sdr_poc)**
(FPGA accelerators for SDR with LiteX).

<img src="https://user-images.githubusercontent.com/1450143/179495534-4c54973b-9203-4893-9eaa-d9177413e9bf.png" width="500">

Tests and bring-ups that became reference material: [litex_mister_test](https://github.com/enjoy-digital/litex_mister_test)
(MiSTer on a Cyclone V HPS), [litex_agilex5_test](https://github.com/enjoy-digital/litex_agilex5_test),
[aduivo_forgix_test](https://github.com/enjoy-digital/aduivo_forgix_test), [litepcie_ptm_test](https://github.com/enjoy-digital/litepcie_ptm_test),
[litex_openwrt_test](https://github.com/enjoy-digital/litex_openwrt_test), [fk33_hbm2_test](https://github.com/enjoy-digital/fk33_hbm2_test),
[litex_verilog_axi_test](https://github.com/enjoy-digital/litex_verilog_axi_test), [litex_soc_gen_test](https://github.com/enjoy-digital/litex_soc_gen_test),
[litex_vexriscv_smp_usb_host_test](https://github.com/enjoy-digital/litex_vexriscv_smp_usb_host_test), and the others under
[github.com/enjoy-digital](https://github.com/enjoy-digital?tab=repositories).

Two of them in pictures: the alternative firmware/gateware of the SDS1104X-E scope
([360nosc0pe](https://github.com/360nosc0pe/scope)) and the HBM2 test infrastructure on the Forest Kitten 33.

<img src="https://user-images.githubusercontent.com/1450143/124901562-6977e480-dfe2-11eb-9071-4344d1146968.png" width="420"> <img src="https://user-images.githubusercontent.com/1450143/124902018-d4c1b680-dfe2-11eb-89c4-8b498605c34d.png" width="300">

## LiteX-Hub collaborative projects

[LiteX-Hub](https://github.com/litex-hub) hosts the repositories maintained with and by the
community:

| Project | What it is |
| --- | --- |
| [litex-boards](https://github.com/litex-hub/litex-boards) | The platforms and targets of 250+ boards from 9 FPGA vendors ([Add a new board](Add-A-New-Board.md)). |
| [linux-on-litex-vexriscv](https://github.com/litex-hub/linux-on-litex-vexriscv), [linux-on-litex-rocket](https://github.com/litex-hub/linux-on-litex-rocket) | Linux on LiteX SoCs ([Run Linux](Run-Linux-On-Your-SoC.md)). |
| [litespi](https://github.com/litex-hub/litespi), [litei2c](https://github.com/litex-hub/litei2c), [litehyperbus](https://github.com/litex-hub/litehyperbus), [litevideo](https://github.com/litex-hub/litevideo) | Cores maintained in the hub (the last two superseded by LiteX's HyperRAM and video cores). |
| [zephyr-on-litex-vexriscv](https://github.com/litex-hub/zephyr-on-litex-vexriscv) | The SoC builder of the Zephyr `litex_vexriscv` platform (Antmicro). |
| [fpga_101](https://github.com/litex-hub/fpga_101) | Lessons and labs to learn FPGAs with Migen/LiteX ([Tutorials](Tutorials-Resources.md)). |
| [pythondata-cpu-*](https://github.com/litex-hub?q=pythondata-cpu), [pythondata-software-*](https://github.com/litex-hub?q=pythondata-software), [pythondata-misc-*](https://github.com/litex-hub?q=pythondata-misc) | The packaged sources of the 27 CPUs, picolibc and compiler-rt, and misc cores (USB OHCI, tapcfg), generated with [pythondata-auto](https://github.com/litex-hub/pythondata-auto). |
| [wishbone-utils](https://github.com/litex-hub/wishbone-utils) | `wishbone-tool`, a Rust client for the bridges (Fomu heritage). |
| [litex-renode](https://github.com/litex-hub/litex-renode), [cocotb_verilator_sim_example](https://github.com/litex-hub/cocotb_verilator_sim_example) | Simulation helpers and examples. |
| [micropython](https://github.com/litex-hub/micropython), [linux](https://github.com/litex-hub/linux), [opensbi](https://github.com/litex-hub/opensbi), [picolibc](https://github.com/litex-hub/picolibc), [barebox](https://github.com/litex-hub/barebox) | The forks carrying the LiteX ports and patches. |

## Community projects built with LiteX

Organizations and companies:

| Project | What it is |
| --- | --- |
| [Betrusted / Precursor](https://github.com/betrusted-io/betrusted-soc) and [Xous](https://github.com/betrusted-io/xous-core) | bunnie's open secure communicator: two LiteX SoCs (the Spartan-7 secure domain and the iCE40 embedded controller) running the Xous microkernel. |
| [Antmicro](https://antmicro.com): [rowhammer-tester](https://github.com/antmicro/rowhammer-tester), [RDIMM](https://github.com/antmicro/rdimm-ddr5-tester)/[SO-DIMM DDR5 testers](https://github.com/antmicro/sodimm-ddr5-tester), [LPDDR4 test board](https://github.com/antmicro/lpddr4-test-board), [SDI-MIPI bridge](https://github.com/antmicro/sdi-mipi-bridge), [Renode](https://github.com/renode/renode) | DRAM test platforms built on LiteDRAM (DDR4/DDR5/LPDDR4 PHYs contributed upstream), a video converter, and the Renode simulator's LiteX support. |
| [Google CFU Playground](https://github.com/google/CFU-Playground) | Custom function units for ML on VexRiscv in LiteX SoCs. |
| [Efabless Caravel management SoC](https://github.com/efabless/caravel_mgmt_soc_litex) | The management SoC of the Caravel ASIC harness (SkyWater/OpenMPW) is a LiteX SoC. |
| [MyriadRF LimeSDR_GW](https://github.com/myriadrf/LimeSDR_GW), [LimePSB RPCM](https://github.com/myriadrf/LimePSB_RPCM_GW) | The LiteX gateware of Lime Microsystems' SDR boards. |
| [EEVengers ThunderScope](https://github.com/EEVengers/thunderscope_litex) | The oscilloscope's PCIe/Thunderbolt gateware. |
| [SpinalHDL VexRiscv](https://github.com/SpinalHDL/VexRiscv), [NaxRiscv](https://github.com/SpinalHDL/NaxRiscv), [VexiiRiscv](https://github.com/SpinalHDL/VexiiRiscv) | The CPUs most used with LiteX, developed with LiteX as a main integration target. |
| [MiSTeX](https://github.com/MiSTeX-devel/MiSTeX-ports) | The MiSTer retro-computing cores on other FPGA boards, with LiteX. |
| [Fomu](https://github.com/im-tomu/foboot) and its [workshop](https://github.com/im-tomu/fomu-workshop), [OrangeCrab examples](https://github.com/orangecrab-fpga/orangecrab-examples), [iCEBreaker LiteX examples](https://github.com/icebreaker-fpga/icebreaker-litex-examples) | Small open boards whose reference designs and workshops are LiteX SoCs. |
| [F4PGA examples](https://github.com/chipsalliance/f4pga-examples) | LiteX designs as benchmarks of the open-source Xilinx flow (CHIPS Alliance). |
| [Signaloid C0-microSD](https://github.com/signaloid/Signaloid-C0-microSD-litex-integration), [iCE40 I2C integration](https://github.com/signaloid/iCE40-I2C-LiteX-integration) | LiteX integrations on Signaloid's iCE40 modules. |
| [TimVideos HDMI2USB](https://github.com/timvideos/HDMI2USB-litex-firmware), [litex-buildenv](https://github.com/timvideos/litex-buildenv) | The video capture firmware and build environment that grew the early community (legacy). |

Individuals and smaller projects: [LiteX-CNC](https://github.com/Peter-van-Tol/LiteX-CNC) and
[litehm2](https://github.com/sensille/litehm2) (LinuxCNC on LiteX boards),
[openfpga-litex](https://github.com/agg23/openfpga-litex) (a RISC-V platform for the Analogue
Pocket), [icepi-zero-c64](https://github.com/m1nl/icepi-zero-c64) and [gamebub-litex](https://github.com/AEW2015/gamebub-litex)
(retro consoles), [litex_imgui_usb_demo](https://github.com/suarezvictor/litex_imgui_usb_demo)
(soft USB and ImGui), [eurorack-pmod-litex](https://github.com/apfaudio/eurorack-pmod-litex)
(audio DSP with Rust firmware), [rust-litex-hal](https://github.com/pepijndevos/rust-litex-hal) and
[rust-litex](https://github.com/tomtor/rust-litex) (Rust on LiteX), [SucreLA](https://github.com/fallen/SucreLA)
(a logic analyzer), [hBPF](https://github.com/rprinz08/hBPF) (eBPF in hardware),
[litex-template](https://github.com/sergachev/litex-template) (a project template, Zynq/ZynqMP
workflows), [nix-litex](https://github.com/lschuermann/nix-litex) (Nix packaging),
[LiteInjector](https://github.com/labsticc-arcad/LiteInjector) (fault injection, Lab-STICC),
[liteethercat](https://github.com/romanetz/liteethercat) (EtherCAT slave), [ledwall](https://github.com/siegeld/ledwall),
[probehive](https://github.com/JanHaan/probehive) (a multi-target CMSIS-DAP probe),
[tang_computer](https://github.com/kami4ka/tang_computer) (Linux on the Tang Primer 20K),
[begonia-pciesim](https://github.com/jingyi-iii/begonia-pciesim) (LitePCIe + QEMU co-simulation),
[panog2_linux](https://github.com/skiphansen/panog2_linux) (Linux on Pano Logic G2),
[Chubby75](https://github.com/q3k/chubby75) (the reverse-engineered Colorlight boards),
[A Trustworthy, Libre, Self-Hosting 64-bit RISC-V Linux Computer](https://www.contrib.andrew.cmu.edu/~somlo/BTCP/)
(Rocket + LiteX, building its own bitstream with the open toolchain). The
[`litex` topic on GitHub](https://github.com/topics/litex) has more.
