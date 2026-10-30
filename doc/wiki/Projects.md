What people build with LiteX: our clients' systems first (they fund the development), then
our own projects, the LiteX-Hub repositories, what the community built elsewhere and, since
2026, what coding agents build with it. Yours is missing?
[Send a pull request](Contributing-to-the-Wiki.md) with a line and a link.

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
firmware were developed with an AI agent guided by Enjoy-Digital.

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
| [pythondata-cpu-*](https://github.com/litex-hub?q=pythondata-cpu), [pythondata-software-*](https://github.com/litex-hub?q=pythondata-software), [pythondata-misc-*](https://github.com/litex-hub?q=pythondata-misc) | The packaged sources of the CPUs, picolibc, compiler-rt and misc cores ([pythondata-auto](https://github.com/litex-hub/pythondata-auto) makes them). |
| [wishbone-utils](https://github.com/litex-hub/wishbone-utils) | `wishbone-tool`, a Rust client for the bridges (Fomu heritage). |
| [litex-renode](https://github.com/litex-hub/litex-renode), [cocotb_verilator_sim_example](https://github.com/litex-hub/cocotb_verilator_sim_example) | Simulation helpers and examples. |
| [micropython](https://github.com/litex-hub/micropython), [linux](https://github.com/litex-hub/linux), [opensbi](https://github.com/litex-hub/opensbi), [picolibc](https://github.com/litex-hub/picolibc), [barebox](https://github.com/litex-hub/barebox) | The forks carrying the LiteX ports and patches. |

## Community projects built with LiteX

Organizations and companies:

| Project | What it is |
| --- | --- |
| [Betrusted / Precursor](https://github.com/betrusted-io/betrusted-soc) and [Xous](https://github.com/betrusted-io/xous-core) | bunnie's open secure communicator: two LiteX SoCs (Spartan-7, iCE40) running the Xous microkernel. |
| [Antmicro](https://antmicro.com): [rowhammer-tester](https://github.com/antmicro/rowhammer-tester), [RDIMM](https://github.com/antmicro/rdimm-ddr5-tester)/[SO-DIMM DDR5 testers](https://github.com/antmicro/sodimm-ddr5-tester), [LPDDR4 test board](https://github.com/antmicro/lpddr4-test-board), [SDI-MIPI bridge](https://github.com/antmicro/sdi-mipi-bridge), [Renode](https://github.com/renode/renode) | DRAM testers on LiteDRAM (their DDR4, DDR5 and LPDDR4 PHYs are upstream), a video converter, Renode. |
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

## Projects built with AI agents

Two projects of autumn 2026 belong to a new category: the human set the goals and ran the
board, a coding agent wrote the hardware. Both picked LiteX on their own, with the comparison
written down, and both show which parts of the ecosystem an agent reaches for.

### mmRISC-2: a 64-bit RISC-V CPU that boots Linux, designed by Claude Code

[mmRISC-2](https://github.com/munetomo-maruyama/mmRISC-2) is Munetomo Maruyama's second
home-made RISC-V core: RV64GC with the bit-manipulation extensions, an 8-stage pipeline, an
Sv39 MMU, a pipelined FPU, 16 KB L1 caches and a 256 KB L2, JTAG/cJTAG debug, performance
counters usable with `perf`. On an Arty A7-100T at 50 MHz it boots LiteX BIOS, OpenSBI and
Linux 7.2 from the SD card, Ethernet works, and Debian 13 compiles C programs on the board
itself.

Everything in the repository (the specifications, the RTL, the testbenches with reference
models and bug injection, the scripts, the documents in two languages) was written by Claude
Code between 2026-09-13 and 10-19. The author set the goals, chose among the options it
proposed, ran Vivado and the board and passed the results back. The
[white paper](https://github.com/munetomo-maruyama/mmRISC-2/blob/main/Doc/20261020_WhitePaper_mmRISC-2.pdf)
tells how it went, day by day.

<p align="center"><img src="https://raw.githubusercontent.com/munetomo-maruyama/mmRISC-2/main/Doc/src/figs/fig_soc_en.svg" width="760"></p>

<img align="right" src="https://raw.githubusercontent.com/munetomo-maruyama/mmRISC-2/main/Doc/src/figs/fpga_board.jpg" width="230">

The first prompt asked the agent whether to start from LiteX, vivado-risc-v or another base.
Its answer, as the white paper summarizes it: LiteX, because it has a mechanism for swapping
CPUs with the existing CPUs as examples, an official Arty A7 target with DDR3, Ethernet and SD
card, and OpenSBI and the device tree already in place. Linux booted on the standard Rocket
configuration the same day, as the reference; from there the task was "replace only the CPU".

The core is a [`core.py`](https://github.com/munetomo-maruyama/mmRISC-2/blob/main/LitexSystem/cpu/mmrisc/core.py)
in the project's own tree: LiteX collects every directory holding one from the working
directory, so `--cpu-type mmrisc` works and the LiteX checkout stays untouched. AXI4 goes to
LiteDRAM and AXI-Lite to the peripherals, the SD card and Ethernet DMAs are routed through the
data cache so that coherence is kept in hardware, and LiteX's L2 is disabled in favour of the
CPU's own.

From the pipeline skeleton to the integration in LiteX took two days; the BIOS came up on the
board on 09-24 and Linux on 09-25. The real `bios.bin`, run in the agent's testbench with a
model of the UART, reproduced the first board bug and stayed as the regression test. The
author's conclusion: setting "make only the CPU, reuse everything else" at the very beginning
is one of the main reasons the project reached Linux so quickly.

### openTPU: an LLM accelerator that moved from the Xilinx MIG to LiteDRAM

[openTPU](https://github.com/FeSens/openTPU) (Felipe Sens Bonetto) is "an open-source AI
accelerator, developed by AI": the SystemVerilog, the instruction set, a bit-exact simulator, a
kernel language and its compiler, a profiler and the host software in one Apache-2.0 monorepo,
plus an ASIC flow on Yosys and OpenROAD.

It runs Qwen3, Qwen3.5, LFM2, Gemma 4, SmolLM3 and Phi-4-mini with their real weights on a
Kintex-7 PCIe card (an Inspur YPCB-00338: xc7k480t, two DDR3 channels, Xilinx XDMA for PCIe),
and the card produces the same tokens as the simulator, bit for bit. Decode is bound by DRAM
bandwidth, which is where LiteDRAM comes in.

![otpu-chat running LFM2.5-230M on the card, with otpu-smi watching it](https://raw.githubusercontent.com/FeSens/openTPU/main/docs/img/card-chat-smi.gif)

The production images used two Xilinx MIGs behind a SmartConnect. The project's
[LiteDRAM study](https://github.com/FeSens/openTPU/blob/main/docs/litedram.md) asked whether
LiteDRAM could replace them, and listed why it should:

- the memory path cost about 28% of the design's LUTs;
- the MIG's AXI front end charged controller cycles per transaction, where LiteDRAM's native
  port pipelines commands with no per-transaction cost;
- calibration runs in software, so the host or a small CPU can drive it;
- the controller is RTL that can be read and simulated with the rest of the design.

The switch took the last days of September 2026. The core comes out of LiteDRAM's generator
with a PHY derived from the Artix-7 one (the banks have no ODELAY, so write leveling moves CK
with the MMCM's fine phase shift) and two native ports per channel behind the ECC frontend. A
VexRiscv `minimal` with 16 KB of RAM sits inside the memory core and calibrates both channels
in 12 s at power-up, with LiteX's `sdram.c` as the reference for its firmware.

Along the way the controller was measured cycle by cycle in Migen with a DFI stub PHY, one
channel was exported to Verilog to co-simulate with the accelerator under Verilator, LiteDRAM's
BIST ran the first tests on the card, JTAGBone stood in for the PCIe BAR during bring-up, and a
copy of the multiplexer was tuned for the accelerator's traffic. The LiteDRAM image first
decoded within 2.3% of the MIG image, then faster: 90 to 94% of the DDR3 peak once tuned.

### What they reach for, and why

We did not design LiteX for agents. We designed it so that one person can build a complete SoC
from a terminal, in Python, and read everything it generates. It turns out this is what an
agent needs too.

A vendor memory controller comes out of a wizard, with its calibration in a hardware state
machine; LiteDRAM is `crossbar.py`, `bankmachine.py`, a generator, a Migen simulation and a
calibration routine in C, so an agent can measure it, modify it and port its calibration to a
CPU of its own. A SoC is a target file, with the 250+ boards of LiteX-Boards to compare
against; a CPU is a `core.py`, with the in-tree CPUs as examples; the BIOS boots in Verilator
and on the board from the same binary; the host bridges let a Python script, or the agent,
read the board.

The parts these two reached for first:

- [LiteDRAM](https://github.com/enjoy-digital/litedram), its generator and its BIST;
- the [CPU plug-in mechanism](Add-A-New-CPU.md) and the LiteX-Boards targets;
- the [BIOS](BIOS.md), in simulation and on the board;
- [`litex_sim`](SoC-Simulator.md) and the Migen simulation of a core;
- [JTAGBone](Host-Bridges.md) for the first access to the board.

[LiteX for AI agents](LiteX-for-AI-Agents.md) is the map we wrote for the next one. If your
agent built something with LiteX, add it here.

## Next

- [Feedback, contribution, support](Feedback-Contribution-Support.md): custom developments and support for your own project.
- [Cores ecosystem](Cores-Ecosystem.md): the cores these projects are built on.
- [Tutorials and resources](Tutorials-Resources.md): the projects documented as tutorials.
- [LiteX on the Acorn CLE 215+](Use-LiteX-on-the-Acorn-CLE-215.md): the cheapest way to join.
