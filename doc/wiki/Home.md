<p align="center"><img src="https://raw.githubusercontent.com/enjoy-digital/litex/master/doc/litex.png"></p>

```
             Copyright 2012-2026 / Enjoy-Digital & LiteX developers
```

<!-- readme:begin -->
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
 - :heavy_check_mark: Powerful debug infrastructure through the various [bridges](Host-Bridges.md) and [LiteScope](https://github.com/enjoy-digital/litescope).
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
Your design is two Python files: the *platform* describes the board (pins, clocks, connectors, toolchain, programmer) and the *target* describes your SoC (CPU, memories, peripherals, cores from the ecosystem); [LiteX-Boards](https://github.com/litex-hub/litex-boards) has 250+ of them. The Builder generates the Verilog and the constraints, runs the toolchain (or Verilator), builds the BIOS and writes the software support: `csr.h`, `soc.h`, `mem.h`, `memory.x`, `csr.csv/json/svd`, the device trees. The host tools (`litex_term`, `litex_server` and `litex_cli` through a UART, JTAG, Ethernet or PCIe bridge, LiteScope, GDB) then control and debug the running SoC.

# Try it in ten minutes

```sh
python3 -m venv ~/litex-venv && source ~/litex-venv/bin/activate
wget https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py
chmod +x litex_setup.py
./litex_setup.py --init --install --config=standard   # Migen, LiteX, the cores, the boards, the CPUs
./litex_setup.py --gcc=riscv                           # the RISC-V compiler for the BIOS and software
pip3 install meson ninja
litex_sim --cpu-type=vexriscv                          # a SoC in Verilator, no board needed
```

![litex_sim: the BIOS boots in the terminal](images/litex-sim-boot.svg)

That is a VexRiscv SoC running in Verilator, the LiteX BIOS at its prompt in your terminal.
Next:

1. [Install LiteX](Installation.md): the toolchains, your board, updates, troubleshooting.
2. [Create a minimal SoC](Create-A-minimal-SoC.md): the same SoC on your board, from a 40-line Python file.
3. [Write firmware for it](Write-Firmware-For-Your-SoC.md): the bare-metal demo, built and loaded over the serial port.
4. [Control it from the host](Host-Bridges.md): read and write the SoC from Python scripts.
5. [Look inside with LiteScope](Use-LiteScope-To-Debug-A-SoC.md): a logic analyzer inside the design.
6. [Debug the CPU with GDB](Debug-With-GDB.md): breakpoints in the firmware over JTAG.

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
| **Build your SoC** | [Add a new board](Add-A-New-Board.md), [Add a new core](Add-A-New-Core.md), [Add a new CPU](Add-A-New-CPU.md), [Reuse an existing core](Reuse-An-Existing-Core.md), [Create a complex SoC](Create-A-Complex-SoC.md), [Create a PCIe SoC](Create-A-PCIe-SoC.md), [Export to Verilog](Export-To-Verilog.md), [Simulate your SoC](SoC-Simulator.md), [Load and flash](Load-And-Flash.md), [LiteX on the Acorn CLE 215+](Use-LiteX-on-the-Acorn-CLE-215.md) |
| **Run software on it** | [OSes ecosystem](OSes-Ecosystem.md), [BIOS](BIOS.md), [MicroPython](Run-MicroPython-On-Your-SoC.md), [Zephyr](Run-Zephyr-On-Your-SoC.md), [Linux](Run-Linux-On-Your-SoC.md) |
| **How LiteX works** | [The LiteX approach](LiteX-Approach.md), [SoC builder](SoC-builder.md), [Choosing a CPU](Choosing-A-CPU.md), [Wishbone](Wishbone-Bus.md) / [AXI](AXI-Bus.md) / [CSR](CSR-Bus.md) buses, [Streams](Streams.md), [Verilog to LiteX](LiteX-for-Hardware-Engineers.md) |
| **Reference** | [CPUs](CPUs.md), [Hard core CPUs](Hard-core-CPUs.md), [SoC builder reference](SoC-Builder-Reference.md), [Cores](Cores.md), [Cores ecosystem](Cores-Ecosystem.md), [Build backends](Build-Backends.md), [Tools](Tools.md), [SoC documentation](SoC-Documentation.md) |
| **Projects and community** | [Projects](Projects.md), [Tutorials and resources](Tutorials-Resources.md), [Feedback, contribution, support](Feedback-Contribution-Support.md), [Contributing to the wiki](Contributing-to-the-Wiki.md) |
| **For AI agents** | [LiteX for AI agents](LiteX-for-AI-Agents.md) |
<!-- readme:end -->
