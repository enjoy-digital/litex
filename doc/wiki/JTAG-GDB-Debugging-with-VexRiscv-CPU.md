[> Description/Requirements
---------------------------

![](https://user-images.githubusercontent.com/1450143/166491365-62846a9e-8c08-4dc3-b45d-35353c1c6fc0.png)

It is possible to use GDB with VexRiscv CPU on LiteX SoCs; this requires a specific  configuration of the CPU/SoC and a specific OpenOCD version:
 - A debug variant of VexRiscv CPU has to be used (`+debug`).
 - A [LiteX bridge](Use-Host-Bridge-to-control-debug-a-SoC.md) has to be added to the SoC to provides a Host <-> FPGA bridge used to tunnel GDB.
 - A specific version of [OpenOCD](https://github.com/SpinalHDL/openocd_riscv) from SpinalHDL.

One of the advantage of tunneling GDB over a LiteX bridge is that LiteX-Term and Python scripts can still be used during GDB debug with a single bridge, enabling MMAP writes/reads and LiteScope captures during the GDB session.
 
[> Enable the debug CPU plugin
------------------------------
The debug plugin of VexRiscv is enabled in the LiteX CPU wrapper by adding `+debug` to the variant name. This can be done directly on targets with:

    python3 -m litex_boards.targets.digilent_arty --cpu-type=vexriscv --cpu-variant=standard+debug

or by setting directly `cpu_variant` of `SoCCore`.

 [> Adding a LiteX bridge
-------------------------

To tunnel the GDB, a LiteX bridge has to be setup on the SoC. Visiting this [wiki page](Use-Host-Bridge-to-control-debug-a-SoC.md) will show the different possibilities.

In most cases, tunneling over UART is the more convenient.  This can be enabled on targets by switching the UART to the Crossover mode and enabling UARTBone. This can be done directly on targets with:

	python3 -m litex_boards.targets.digilent_arty --uart-name=crossover+uartbone

or by setting directly `uart_name` of `SoCCore`.

 [> Getting/Compiling SpinalHDL's OpenOCD
-----------------------------------------

A specific version of [OpenOCD](https://github.com/SpinalHDL/openocd_riscv) from SpinalHDL has to be used.

This can be retrieved/compiled with:

    git clone https://github.com/SpinalHDL/openocd_riscv.git
    cd openocd_riscv
    wget https://raw.githubusercontent.com/litex-hub/pythondata-cpu-vexriscv/master/pythondata_cpu_vexriscv/verilog/VexRiscv_Debug.yaml
    mv VexRiscv_Debug.yaml cpu0.yaml
    ./bootstrap
    ./configure --enable-dummy
    make

 [> Example
-----------

**Build the SoC:**
From the previous instructions, let's build the SoC on the Digilent Arty with the VexRiscv debug plugin enabled and a UARTBone bridge:

    python3 -m litex_boards.targets.digilent_arty --cpu-type=vexriscv --cpu-variant=standard+debug --uart-name=crossover+uartbone --csr-csv=csr.csv --build --load

**Start LiteX-Server**:
With the SoC built and loaded to the FPGA board, let's start LiteX Server:

    litex_server --uart --uart-port=/dev/ttyUSBX

**Start OpenOCD Server** (from OpenOCD directory):

    ./src/openocd -c 'interface dummy' \
                  -c 'adapter_khz 1' \
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

    riscv64-unknown-elf-gdb build/efinix_titanium_ti60_f225_dev_kit/software/bios/bios.elf -ex 'target remote localhost:3333'

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
    Reading symbols from build/efinix_titanium_ti60_f225_dev_kit/software/bios/bios.elf...
    Remote debugging using localhost:3333
    _start () at /home/florent/dev/litex/litex/litex/soc/cores/cpu/vexriscv/crt0.S:6
    6	  j crt_init
    (gdb)

**Start LiteX-Term** (from target build directory):

    litex_term crossover

And you are ready to debug! With GDB and LiteX-Term over a the same UART.
