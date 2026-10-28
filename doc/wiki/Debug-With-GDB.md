## Introduction

This guide explores how to leverage JTAG debugging with LiteX for RISC-V CPUs such as VexRiscv-SMP, NaxRiscv or VexiiRiscv CPUs which are commonly used within LiteX SoCs/projects. We'll look at setting up JTAG for both simulations and physical hardware implementations, using exposed/external JTAG IO pins but also internal features like BSCANE2 on Xilinx FPGAs.

![](https://github.com/enjoy-digital/litex/assets/1450143/9a652208-58c2-4c96-8ba7-d8330c1b6a54)

- [GDB with RISC-V](#gdb-with-risc-v)
- [Debugging in LiteX Simulation](#debugging-in-litex-simulation)
- [Debugging on Physical Hardware with an External USB/JTAG Cable](#debugging-on-physical-hardware-with-an-external-usbjtag-cable)
- [Debugging on Physical Hardware Directly Through BSCANE2 JTAG Primitive](#debugging-on-physical-hardware-directly-through-bscane2-jtag-primitive)

## GDB with RISC-V

GNU Debugger (GDB) is a powerful tool for debugging programs written in C, C++, and other languages. For RISC-V CPUs, GDB allows developers to control the execution of their program, inspect memory and register states, and perform other critical debugging tasks. GDB interacts with RISC-V through a debugging interface which can be supported via JTAG, enabling step-by-step execution and real-time inspection of the processor state.

To use GDB with RISC-V in a LiteX environment, the processor must be compiled with debugging symbols and the hardware or simulation environment must support debugging capabilities. This setup often involves configuring OpenOCD as a bridge between GDB and the target RISC-V CPU.

## Common Aspects

Accessing the *VexRiscv* CPU via *GDB* necessitates the utilization of *OpenOCD*.
In this page we will uses a couple of files to configure this tool:

1. Interface Configuration File: This file provides specific information and parameters about the
interface required to communicate with the target. It varies according to the particular use case and will be provided for each subsection.
2. Target Configuration File: This file informs OpenOCD about the target, including its
type, instruction register length, and whether direct access to the CPU is available or
through BSCANE2. This file remains relatively consistent across different cases.

The file used to provide information about the target, referred to as `riscv_jtag_tunneled.tcl`
throughout this page, appears as follows:

```tcl
# SPDX-FileCopyrightText: 2023 "Everybody"
#
# SPDX-License-Identifier: MIT

set _CHIPNAME riscv
set _TARGETNAME $_CHIPNAME.cpu
set cpu_count 1
if [info exists env(RISCV_COUNT)]  {
    set cpu_count $::env(RISCV_COUNT)
}

if { [info exists TAP_NAME] } {
    set _TAP_NAME $TAP_NAME
} else {
    set _TAP_NAME $_TARGETNAME
}

adapter speed 500

# external jtag probe
if {$_TAP_NAME eq $_TARGETNAME} {
    jtag newtap $_CHIPNAME cpu -irlen 6 -expected-id 0x10003FFF
}

for {set i 0} {$i < $cpu_count} {incr i} {
  target create $_TARGETNAME.$i riscv -coreid $i -chain-position $_TAP_NAME
  riscv use_bscan_tunnel 6 1
  #riscv set_bscan_tunnel_ir 0x23  #In riscv-openocd upstream
}

for {set i 0} {$i < $cpu_count} {incr i} {
    targets $_TARGETNAME.$i
    init
    halt
}

echo "Ready for Remote Connections"
```

This configuration script initializes the *OpenOCD* session, creating targets for
each CPU instance and ensuring proper communication via *JTAG*. Once initialized,
the CPUs are halted and the system is ready for remote connections.

## Debugging in LiteX Simulation

### Setting Up the Environment

LiteX Sim provides a versatile environment for testing and debugging system designs before deploying them to actual hardware. To initiate a simulation with JTAG debugging:

1. Initialize the Simulation Environment and generate software files

The first step involves initializing the LiteX simulation environment with the specific CPU configuration and debug options. This setup does not yet compile the gateware, as it's primarily focused on preparing the simulation parameters and environment.

```bash
litex_sim --cpu-type=vexriscv_smp --with-sdram --with-rvc --with-privileged-debug --hardware-breakpoints 4 --jtag-tap --with-jtagremote --no-compile-gateware
```
Where:
* `--cpu-type=vexriscv_smp`: Specifies the CPU type to simulate.
* `--with-sdram`: Includes SDRAM in the simulation, used here to store our firmware.
* `--with-rvc`: Enables RISC-V compressed instructions.
* `--with-privileged-debug`: Includes support for privileged debugging features.
* `--hardware-breakpoints 4`: Specifies the number of hardware breakpoints available for use.
* `--jtag-tap`: Includes a JTAG Test Access Port in the simulation.
* `--with-jtagremote`: Allows remove JTAG connection in simulation.
* `--no-compile-gateware`: Skips the compilation of FPGA gateware, focusing on software preparation.

2. Compile the LiteX Bare Metal Demo

After setting up the initial simulation environment, the next step involves compiling a simple bare metal demo program. This demo serves as the primary code base for demonstrating the debugging process.

```bash
litex_bare_metal_demo --build-path=build/sim/
```

Where:
* `--build-path=build/sim/`: Specifies the directory where the simulation environment has been set up.

3. Run the Simulation with the LiteX Bare Metal Demo

Finally, the compiled demo program is used to run the simulation, allowing for real-time debugging and examination of the CPU's behavior under simulated conditions.

```bash
litex_sim --cpu-type=vexriscv_smp --with-sdram --sdram-init demo.bin --with-rvc --with-privileged-debug --hardware-breakpoints 4 --jtag-tap --with-jtagremote
```

Where:
* `--sdram-init demo.bin`: Initializes the SDRAM with demo.bin, the binary file generated from the bare metal demo, effectively loading the program into the simulated system's memory.

### Configuring and using OpenOCD and GDB

### OpenOCD

**Setting up**

File required to communicate with the target (`jtag_remote.cfg`) is:
```cfg
adapter speed 10000
adapter driver remote_bitbang
remote_bitbang host localhost
remote_bitbang port 44853
```

To initiate OpenOCD:
```bash
openocd -f jtag_remote.cfg -f riscv_jtag_tunneled.tcl
```

GDB
To debug using GDB:
```bash
riscv64-unknown-elf-gdb demo/demo.elf
(gdb) target extended-remote localhost:3333
(gdb) load
(gdb) continue
```

**Note**: You may encounter timeouts and slow command executions; adjusting GDB's set remotetimeout may be necessary.

## Debugging on Physical Hardware with an external USB/JTAG cable

For debugging on actual hardware, such as an FPGA board, you can expose JTAG pins and connect them to an external USB-to-JTAG adapter. This method involves specifying JTAG pins on the FPGA and routing them to accessible connectors.

The following example **targets a Digilent Arty board** but can easily be adapted to other hardware:

### Preparing the Target Hardware

To set up JTAG debugging, you first need to update your SoC configuration to expose JTAG pins through one of the PMOD connectors on the Arty board. This is accomplished by adding a new PMOD extension to your SoC configuration and wiring it up to the JTAG interface of the CPU.

```python3
from litex.build.generic_platform import Subsignal, Pins, IOStandard
# Add the JTAG PMOD extension to the FPGA platform
soc.platform.add_extension([
    ("pmod_jtag", 0,
        Subsignal("tms", Pins("pmodd:0")),
        Subsignal("tdi", Pins("pmodd:1")),
        Subsignal("tdo", Pins("pmodd:3")),
        Subsignal("tck", Pins("pmodd:2")),
        IOStandard("LVCMOS33")
    )
])
# Request and connect the JTAG interface
jtag = soc.platform.request("pmod_jtag")
soc.comb += [
    soc.cpu.jtag_clk.eq(jtag.tck),
    soc.cpu.jtag_tms.eq(jtag.tms),
    soc.cpu.jtag_tdi.eq(jtag.tdi),
    jtag.tdo.eq(soc.cpu.jtag_tdo)
]
# Timing constraints for JTAG clock
soc.platform.add_platform_command("create_clock -name jtag_tck -period 20.0 [get_nets jtag_tck]")
soc.platform.add_false_path_constraints(soc.crg.cd_sys.clk, jtag.tck)
```

### Build and Load the Gateware

Compile and load the gateware/firmware onto the FPGA with the JTAG debugging features enabled. This step ensures that the FPGA is correctly programmed and ready for JTAG interaction.

```bash
python3 -m litex_boards.targets.digilent_arty --cpu-type=vexriscv_smp --with-rvc --with-privileged-debug --hardware-breakpoints=4 --jtag-tap --build --load
```
### Setting up OpenOCD

Configure OpenOCD to interface with the FPGA using the appropriate configuration files for the Digilent JTAG-HS2.

Interface configuration (`digilent-hs2.cfg`):
```cfg
# Digilent JTAG-HS2 configuration for OpenOCD
adapter driver ftdi
ftdi vid_pid 0x0403 0x6014
ftdi channel 0
ftdi layout_init 0x00e8 0x60eb
reset_config none
```

Run OpenOCD with the specified configurations:

```bash
openocd -f digilent-hs2.cfg -f riscv_jtag_tunneled.tcl
```

### Connecting GDB for Debugging

Finally, connect GDB to the OpenOCD server to start debugging the FPGA. Use the following commands to initiate a GDB session targeting the remote JTAG interface:

```bash
gdb-multiarch -q demo/demo.elf -ex "target extended-remote localhost:3333"
```

## Debugging on Physical Hardware directly through BSCANE2 JTAG primitive

Want to go even further an external USB/JTAG cable, we also got you covered :)

Using BSCANE2, a built-in JTAG capability of some Xilinx FPGAs, eliminates the need for external wiring. BSCANE2 integrates the JTAG functionality internally, providing a direct interface for debugging tools without consuming physical I/O pins:

### Preparing the Target Hardware

LiteX does it for you: the `--with-cpu-jtag-debug` option (`soc.add_cpu_jtag_debug(chain=4, clk_freq=10e6, clock_domain="sys")` in a target) instantiates the BSCANE2 primitive on the USER4 chain, connects it to the CPU's JTAG instruction interface and adds the timing constraints. `--cpu-jtag-debug-chain` picks another USER chain (JTAGBone uses USER1, both can coexist), `--cpu-jtag-debug-clk-freq` the maximum TCK frequency used for the timing analysis. Zynq devices are not supported (their TAP belongs to the PS).

The equivalent by hand, if you need to see the wiring:

```python3
from litex.soc.cores.jtag import XilinxJTAG
soc.jtag = jtag = XilinxJTAG(XilinxJTAG.get_primitive(soc.platform.device), chain=4, platform=soc.platform)
soc.comb += [
    soc.cpu.jtag_reset.eq(jtag.reset),
    soc.cpu.jtag_capture.eq(jtag.capture),
    soc.cpu.jtag_shift.eq(jtag.shift),
    soc.cpu.jtag_update.eq(jtag.update),
    soc.cpu.jtag_clk.eq(jtag.tck),
    soc.cpu.jtag_tdi.eq(jtag.tdi),
    soc.cpu.jtag_enable.eq(jtag.sel),
    jtag.tdo.eq(soc.cpu.jtag_tdo),
]
```

### Build and Load the Gateware

Compile and load the gateware/firmware onto the FPGA with the JTAG debugging features enabled. This step ensures that the FPGA is correctly programmed and ready for JTAG interaction.

```bash
python3 -m litex_boards.targets.digilent_arty --cpu-type=vexriscv_smp --with-rvc --with-privileged-debug --hardware-breakpoints=4 --with-cpu-jtag-debug --build --load
```

### Setting up OpenOCD

Configure OpenOCD to interface with the FPGA using the appropriate configuration files for the Digilent onboard interface.

Interface configuration (`digilent_arty.cfg`):
```cfg
# SPDX-FileCopyrightText: 2023 "Everybody"
#
# SPDX-License-Identifier: MIT

adapter driver ftdi
ftdi vid_pid 0x0403 0x6010
ftdi channel 0
ftdi layout_init 0x00e8 0x60eb
ftdi tdo_sample_edge falling

reset_config none
adapter speed 5000

source [find cpld/xilinx-xc7.cfg]
source [find cpld/jtagspi.cfg]
```

Run OpenOCD with the specified configurations:

```bash
openocd -f digilent_arty.cfg -c "set TAP_NAME xc7.tap" -f riscv_jtag_tunneled.tcl
```

### Connecting GDB for Debugging

Finally, connect GDB to the OpenOCD server to start debugging the FPGA. Use the following commands to initiate a GDB session targeting the remote JTAG interface:

```bash
gdb-multiarch -q demo/demo.elf -ex "target extended-remote localhost:3333"
```

## CPU debug through any bridge: `--cpu-jtag-debug-transport=csr` and `litex_jtag`

When the FPGA has no free USER chain, no JTAG cable, or the JTAG port is not reachable (a remote board, a PCIe card), the debug TAP can be driven through CSRs over the LiteX [bridge](Host-Bridges.md) instead of the FPGA's JTAG port:

```bash
python3 -m litex_boards.targets.digilent_arty --cpu-type=vexriscv_smp --with-privileged-debug --hardware-breakpoints=4 \
    --with-cpu-jtag-debug --cpu-jtag-debug-transport=csr --with-etherbone --build --load
litex_server --udp                       # or --uart, --jtag, --pcie: any transport
litex_jtag --csr-csv=build/digilent_arty/csr.csv    # an OpenOCD remote_bitbang server on 127.0.0.1:3335
openocd -c "adapter driver remote_bitbang" -c "remote_bitbang host 127.0.0.1" -c "remote_bitbang port 3335" -f riscv.cfg
gdb-multiarch -q demo/demo.elf -ex "target extended-remote localhost:3333"
```

`litex_jtag` bit-bangs the `cpu_jtag_debug` CSRs (`--csr-name` if renamed) through `litex_server` (`--host`, `--port`); slower than a cable, but it works everywhere the bridge does (also from the simulation with `--with-etherbone`).

## CPU options

- **VexRiscv-SMP**: `--with-privileged-debug` (the RISC-V debug module), `--hardware-breakpoints=N`, `--jtag-tap` (an external TAP on pins, as in the first hardware example) or `--with-cpu-jtag-debug` (BSCAN), `--with-swd-debug` (SWD instead of JTAG, with the `swdremote` module in simulation: `--with-swdremote`).
- **NaxRiscv** and **VexiiRiscv**: `--with-jtag-tap` (external TAP on pins) or `--with-jtag-instruction` (the tunneled TAP used by `--with-cpu-jtag-debug`); the same OpenOCD scripts apply.
- The LiteX repository documents the mechanism in [doc/cpu_jtag_debug.md](https://github.com/enjoy-digital/litex/blob/master/doc/cpu_jtag_debug.md); the OpenOCD configuration files of the usual cables are in `prog/` (`openocd_xc7_ft232.cfg`, `openocd_xc7_ft2232.cfg`, `openocd_xc7_ft4232.cfg`).

## VexRiscv: the `+debug` variant with SpinalHDL's OpenOCD

#### Description/Requirements

![](https://user-images.githubusercontent.com/1450143/166491365-62846a9e-8c08-4dc3-b45d-35353c1c6fc0.png)

It is possible to use GDB with VexRiscv CPU on LiteX SoCs; this requires a specific  configuration of the CPU/SoC and a specific OpenOCD version:
 - A debug variant of VexRiscv CPU has to be used (`+debug`).
 - A [LiteX bridge](Host-Bridges.md) has to be added to the SoC to provides a Host <-> FPGA bridge used to tunnel GDB.
 - A specific version of [OpenOCD](https://github.com/SpinalHDL/openocd_riscv) from SpinalHDL.

One of the advantage of tunneling GDB over a LiteX bridge is that LiteX-Term and Python scripts can still be used during GDB debug with a single bridge, enabling MMAP writes/reads and LiteScope captures during the GDB session.
 
#### Enable the debug CPU plugin
The debug plugin of VexRiscv is enabled in the LiteX CPU wrapper by adding `+debug` to the variant name. This can be done directly on targets with:

    python3 -m litex_boards.targets.digilent_arty --cpu-type=vexriscv --cpu-variant=standard+debug

or by setting directly `cpu_variant` of `SoCCore`.

#### Adding a LiteX bridge

To tunnel the GDB, a LiteX bridge has to be setup on the SoC. Visiting this [wiki page](Host-Bridges.md) will show the different possibilities.

In most cases, tunneling over UART is the more convenient.  This can be enabled on targets by switching the UART to the Crossover mode and enabling UARTBone. This can be done directly on targets with:

	python3 -m litex_boards.targets.digilent_arty --uart-name=crossover+uartbone

or by setting directly `uart_name` of `SoCCore`.

#### Getting/Compiling SpinalHDL's OpenOCD

A specific version of [OpenOCD](https://github.com/SpinalHDL/openocd_riscv) from SpinalHDL has to be used.

This can be retrieved/compiled with:

    git clone https://github.com/SpinalHDL/openocd_riscv.git
    cd openocd_riscv
    wget https://raw.githubusercontent.com/litex-hub/pythondata-cpu-vexriscv/master/pythondata_cpu_vexriscv/verilog/VexRiscv_Debug.yaml
    mv VexRiscv_Debug.yaml cpu0.yaml
    ./bootstrap
    ./configure --enable-dummy
    make

#### Example

**Build the SoC:**
From the previous instructions, let's build the SoC on the Digilent Arty with the VexRiscv debug plugin enabled and a UARTBone bridge:

    python3 -m litex_boards.targets.digilent_arty --cpu-type=vexriscv --cpu-variant=standard+debug --uart-name=crossover+uartbone --csr-csv=csr.csv --build --load

**Start LiteX-Server**:
With the SoC built and loaded to the FPGA board, let's start LiteX Server:

    litex_server --uart --uart-port=/dev/ttyUSBX

**Start OpenOCD Server** (from OpenOCD directory):

    ./src/openocd -c 'adapter driver dummy' \
                  -c 'adapter speed 1' \
                  -c 'jtag newtap lx cpu -irlen 4' \
                  -c 'target create lx.cpu0 vexriscv -endian little -chain-position lx.cpu -dbgbase 0xF00F0000' \
                  -c 'vexriscv cpuConfigFile cpu0.yaml' \
                  -c 'vexriscv networkProtocol etherbone' \
                  -c 'init' \
                  -c 'reset halt'

Which should gives:

    Open On-Chip Debugger 0.11.0+dev-02577-g3eee6eb04-dirty (2022-05-03-09:21)
    Licensed under GNU GPL v2
    For bug reports, read
    	http://openocd.org/doc/doxygen/bugs.html
    DEPRECATED! use 'adapter driver' not 'interface'
    Info : only one transport option; autoselect 'jtag'
    DEPRECATED! use 'adapter speed' not 'adapter_khz'
    adapter speed: 1 kHz
    Info : clock speed 1 kHz
    Info : TAP lx.cpu does not have valid IDCODE (idcode=0x0)
    Info : TAP auto0.tap does not have valid IDCODE (idcode=0x80000000)
    Info : TAP auto1.tap does not have valid IDCODE (idcode=0xc0000000)
    Info : TAP auto2.tap does not have valid IDCODE (idcode=0xe0000000)
    Info : TAP auto3.tap does not have valid IDCODE (idcode=0xf0000000)
    Info : TAP auto4.tap does not have valid IDCODE (idcode=0xf8000000)
    Info : TAP auto5.tap does not have valid IDCODE (idcode=0xfc000000)
    Info : TAP auto6.tap does not have valid IDCODE (idcode=0xfe000000)
    Info : TAP auto7.tap does not have valid IDCODE (idcode=0xff000000)
    Info : TAP auto8.tap does not have valid IDCODE (idcode=0xff800000)
    Info : TAP auto9.tap does not have valid IDCODE (idcode=0xffc00000)
    Info : TAP auto10.tap does not have valid IDCODE (idcode=0xffe00000)
    Info : TAP auto11.tap does not have valid IDCODE (idcode=0xfff00000)
    Info : TAP auto12.tap does not have valid IDCODE (idcode=0xfff80000)
    Info : TAP auto13.tap does not have valid IDCODE (idcode=0xfffc0000)
    Info : TAP auto14.tap does not have valid IDCODE (idcode=0xfffe0000)
    Info : TAP auto15.tap does not have valid IDCODE (idcode=0xffff0000)
    Info : TAP auto16.tap does not have valid IDCODE (idcode=0xffff8000)
    Info : TAP auto17.tap does not have valid IDCODE (idcode=0xffffc000)
    Info : TAP auto18.tap does not have valid IDCODE (idcode=0xffffe000)
    Info : TAP auto19.tap does not have valid IDCODE (idcode=0xfffff000)
    Warn : Unexpected idcode after end of chain: 21 0xfffff800
    Error: double-check your JTAG setup (interface, speed, ...)
    Error: Trying to use configured scan chain anyway...
    Error: lx.cpu: IR capture error; saw 0x0f not 0x01
    Warn : Bypassing JTAG setup events due to errors
    Info : starting gdb server for lx.cpu0 on 3333
    Info : Listening on port 3333 for gdb connections
    Error: JTAG scan chain interrogation failed: all ones
    Error: Check JTAG interface, timings, target power, etc.
    Error: Trying to use configured scan chain anyway...
    Error: lx.cpu: IR capture error; saw 0x0f not 0x01
    Warn : Bypassing JTAG setup events due to errors
    Info : Listening on port 6666 for tcl connections
    Info : Listening on port 4444 for telnet connections

Run GDB on `bios.elf` (from target build directory):

    riscv64-unknown-elf-gdb build/digilent_arty/software/bios/bios.elf -ex 'target remote localhost:3333'

which should gives:

    GNU gdb (SiFive GDB 8.3.0-2019.08.0) 8.3
    Copyright (C) 2019 Free Software Foundation, Inc.
    License GPLv3+: GNU GPL version 3 or later <http://gnu.org/licenses/gpl.html>
    This is free software: you are free to change and redistribute it.
    There is NO WARRANTY, to the extent permitted by law.
    Type "show copying" and "show warranty" for details.
    This GDB was configured as "--host=x86_64-linux-gnu --target=riscv64-unknown-elf".
    Type "show configuration" for configuration details.
    For bug reporting instructions, please see:
    <https://github.com/sifive/freedom-tools/issues>.
    Find the GDB manual and other documentation resources online at:
        <http://www.gnu.org/software/gdb/documentation/>.
    
    For help, type "help".
    Type "apropos word" to search for commands related to "word"...
    Reading symbols from build/digilent_arty/software/bios/bios.elf...
    Remote debugging using localhost:3333
    _start () at /home/florent/dev/litex/litex/litex/soc/cores/cpu/vexriscv/crt0.S:6
    6	  j crt_init
    (gdb)

**Start LiteX-Term** (from target build directory):

    litex_term crossover

And you are ready to debug! With GDB and LiteX-Term over a the same UART.

### Notes

- This page is for the plain `vexriscv` CPU and its `+debug` variants (`minimal+debug`, `lite+debug`, `standard+debug`, `full+debug`, `linux+debug`, `secure+debug`, `+hwbp` for hardware breakpoints), whose debug port is reached through the LiteX bridge with the SpinalHDL OpenOCD fork and `VexRiscv_Debug.yaml`. VexRiscv-SMP, NaxRiscv and VexiiRiscv have a standard RISC-V debug module instead: [JTAG/GDB debugging with VexRiscv-SMP, NaxRiscv and VexiiRiscv](Debug-With-GDB.md) (`--with-cpu-jtag-debug`, `litex_jtag`).
- Any [bridge](Host-Bridges.md) works for the debug transport: `--with-uartbone` as above, `--with-jtagbone` (`litex_server --jtag`, no pins) or `--with-etherbone` (`litex_server --udp`).
