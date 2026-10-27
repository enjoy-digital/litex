# LiteX installation guide

1. Install Python 3.6+ and FPGA vendor's development tools and/or [Verilator](http://www.veripool.org/).
2. Install Migen/LiteX and the LiteX's cores:

```sh
$ wget https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py
$ chmod +x litex_setup.py
$ ./litex_setup.py --init --install --user (--user to install to user directory)
```
  Later, if you need to update all repositories:
```sh
$ ./litex_setup.py --update
```

Release tag can also be specified to update/install specific release of LiteX, ex:
```sh
$ ./litex_setup.py --tag=2022.04 --update
```

> **Note:** On MacOS, make sure you have [HomeBrew](https://brew.sh) installed. Then do, ``brew install wget``.

> **Note:** On Windows, make sure you have `make` and/or `GnuWin` installed and it's possible you'll have to set `SHELL` environment variable to `SHELL=cmd.exe`.

3. Install a RISC-V toolchain (Only if you want to test/create a SoC with a CPU):
```sh
$ pip3 install meson
$ ./litex_setup.py --gcc=riscv
```

4. Build the target of your board...:

Go to litex-boards/litex_boards/targets and execute the target you want to build.

5. ... and/or install [Verilator](http://www.veripool.org/) and test LiteX directly on your computer without any FPGA board:

On Linux (Ubuntu):
```sh
$ sudo apt install libevent-dev libjson-c-dev verilator
$ litex_sim --cpu-type=vexriscv
```

On MacOS:
```sh
$ brew install json-c verilator libevent
$ litex_sim --cpu-type=vexriscv
```
6. Run a terminal program on the board's serial port at 115200 8-N-1.

  You should get the BIOS prompt like the one below.

<p align="center"><img src="https://raw.githubusercontent.com/enjoy-digital/litex/master/doc/bios_screenshot.png"></p>
