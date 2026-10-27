## Introduction

This guide explores how to leverage JTAG debugging with LiteX for RISC-V CPUs such as VexRiscv-SMP, NaxRiscv or future VexiiRiscv CPUs which are commonly used within LiteX SoCs/projects. We'll look at setting up JTAG for both simulations and physical hardware implementations, using exposed/external JTAG IO pins but also internal features like BSCANE2 on Xilinx FPGAs.

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
remote_bitbang_host localhost
remote_bitbang_port 44853
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
soc.platform.add_platform_command("create_clock -period 10.000 -name jtag_tck [get_nets jtag_tck_IBUF]")
soc.platform.add_platform_command("create_clock -name jtag_tck -period 20.0 [get_nets jtag_tck]")
soc.platform.add_false_path_constraints(soc.crg.cd_sys.clk, jtag.tck)
```

### Build and Load the Gateware

Compile and load the gateware/firmware onto the FPGA with the JTAG debugging features enabled. This step ensures that the FPGA is correctly programmed and ready for JTAG interaction.

```bash
./digilent_arty.py --cpu-type=vexriscv_smp --with-rvc --with-privileged-debug --hardware-breakpoints 4 --jtag-tap --build --load
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

```python3
from litex.soc.cores.jtag import XilinxJTAG
soc.jtag = jtag = XilinxJTAG(XilinxJTAG.get_primitive(soc.platform.device), chain=4)
soc.comb += [
    soc.cpu.jtag_reset.eq(jtag.reset),
    soc.cpu.jtag_capture.eq(jtag.capture),
    soc.cpu.jtag_shift.eq(jtag.shift),
    soc.cpu.jtag_update.eq(jtag.update),
    soc.cpu.jtag_clk.eq(jtag.tck),
    soc.cpu.jtag_tdi.eq(jtag.tdi),
    soc.cpu.jtag_enable.eq(True),
    jtag.tdo.eq(soc.cpu.jtag_tdo),
]
```

### Build and Load the Gateware

Compile and load the gateware/firmware onto the FPGA with the JTAG debugging features enabled. This step ensures that the FPGA is correctly programmed and ready for JTAG interaction.

```bash
./digilent_arty.py --cpu-type=vexriscv_smp --with-rvc  --with-privileged-debug --hardware-breakpoints 4 --build --load
```

### Setting up OpenOCD

Configure OpenOCD to interface with the FPGA using the appropriate configuration files for the Digilent onboard interface.

Interface configuration (`digilent_arty.cfg`):
```cfg
# SPDX-FileCopyrightText: 2023 "Everybody"
#
# SPDX-License-Identifier: MIT

adapter driver ftdi
ftdi_vid_pid 0x0403 0x6010
ftdi_channel 0
ftdi_layout_init 0x00e8 0x60eb
ftdi_tdo_sample_edge falling

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
