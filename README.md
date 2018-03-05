```
                       __   _ __      _  __
                      / /  (_) /____ | |/_/
                     / /__/ / __/ -_)>  <
                    /____/_/\__/\__/_/|_|
                         Migen inside

                Build your hardware, easily!
              Copyright 2012-2018 / EnjoyDigital
```


Intro
=====

LiteX is an alternative to [MiSoC](https://github.com/m-labs/misoc) maintained
and used by [Enjoy-Digital](https://enjoy-digital.fr) (and others like
[TimVideos](https://hdmi2usb.tv)) to build our cores, integrate them in
complete SoC and load/flash them to the hardware and experiment new features.

(The LiteX structure is kept close to MiSoC to allow collaboration)

Typical LiteX design flow
--------------------------

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

Sub-packages
------------

* [gen](litex/gen) -
  Provides specific or experimental modules to generate HDL that are not integrated
  in Migen.

* [build](litex/build) -
  Provides tools to build FPGA bitstreams (interface to vendor toolchains) and to
  simulate HDL code or full SoCs.

* [soc](litex/soc) -
  Provides definitions/modules to build cores (bus, bank, flow), cores and tools
  to build a SoC from such cores.

* [boards](litex/boards) -
  Provides platforms and targets for the supported boards.


External Packages
-----------------

Migen documentation can be found here: https://m-labs.hk/migen/manual


Quick start guides
==================

Very Quick start guide for newcomers
------------------------------------

[TimVideos.us](https://code.timvideos.us) has done an awesome job for setting
up a LiteX environment easily in the
[litex-buildenv repo](https://github.com/timvideos/litex-buildenv). It's
recommended for newcomers to go this way.

It has the following features useful for beginners;

 * Completely self contained development environment with almost all
   dependencies needed.
 * Support for various FPGA boards and multiple examples provided!
 * Run different firmware including baremeal, Linux or MicroPython on your
   design.
 * Emulate features of your FPGA using QEMU.

Quick start guide with Conda
----------------------------

 0. Get miniconda by following instructions at https://conda.io/miniconda.html

 1. Clone LiteX
    ```shell
    git clone --recurse-submodules https://github.com/enjoy-digital/litex.git
    ```

 2. Create a LiteX environment from [environment.yml](environment.yml)
    ```shell
    conda env create -f environment.yml
    ```

 3. Enter conda environment
    ```shell
    conda activate litex
    ```

 4. Build the target of your board...:
    Go to [boards/targets](litex/boards/targets) and run the target you want to
    build. For example;
    ```
    cd litex/boards/targets; python arty.py --help
    ```

Quick start guide for advanced users
------------------------------------

 0. If cloned from Git without the --recursive option, get the submodules:
    ```shell
    git submodule update --init
    ```

 1. Install Python 3.5, Migen and FPGA vendor's development tools.
    Get Migen from: https://github.com/m-labs/migen

 2. Compile and install binutils. Take the latest version from GNU.
    ```shell
    mkdir build && cd build
    ../configure --target=lm32-elf
    make
    make install
    ```

 3. (Optional, only if you want to use a lm32 CPU in you SoC)
    Compile and install GCC. Take gcc-core and gcc-g++ from GNU
    (version 4.5 or >=4.9).
    ```shell
    rm -rf libstdc++-v3
    mkdir build && cd build
    ../configure --target=lm32-elf --enable-languages="c,c++" --disable-libgcc \
      --disable-libssp
    make
    make install
    ```

 4. Build the target of your board...:
    Go to [boards/targets](litex/boards/targets) and run the target you want to
    build. For example;
    ```shell
    cd litex/boards/targets; python arty.py --help
    ```

 5. ... and/or install Verilator and test LiteX on your computer:

   * Download and install Verilator: http://www.veripool.org/
   * Install libevent-devel / json-c-devel packages
   * Go to [boards/targets](litex/boards/targets)
   * Run `./sim.py`

 6. Run a terminal program on the board's serial port at 115200 8-N-1.
    You should get the BIOS prompt.


Contact
=======

For questions about
[LiteX Build Environment](https://github.com/timvideos/litex-buildenv)
please use the
[TimVideos contact details here](https://github.com/timvideos/litex-buildenv#contact)

For direct questions about LiteX e-mail: florent [AT] enjoy-digital.fr


License
=======

The majority of code was developed by [EnjoyDigital](http://enjoy-digital.fr)
based off work from [M-Labs](https://m-labs.hk) with contributions from many
other people. It is released under a very liberal [BSD/MIT license](LICENSE).
