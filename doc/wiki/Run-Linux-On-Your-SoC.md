Linux on your board in three steps: build the SoC, get the images, boot them over the serial
port or from an SD card. A LiteX SoC runs Linux when its CPU has an MMU (a `linux` variant or
a 64-bit core, [Choosing a CPU](Choosing-A-CPU.md)), a DRAM (`add_sdram`), a console and a
way to load the images; the SoC description does the rest, since the device tree is generated
from `csr.json`, the kernel has the drivers of the LiteX cores and the BIOS loads the images.
Half an hour with a board that has DRAM, after [the complex SoC](Create-A-Complex-SoC.md).

![A Linux-capable LiteX SoC](images/litex-complex-soc.svg)

*A VexRiscv-SMP with LiteDRAM, LiteEth, LiteSDCard and the usual peripherals: the reference
Linux SoC.*

## 1. Build the SoC

[Linux-on-LiteX-VexRiscv](https://github.com/litex-hub/linux-on-litex-vexriscv) builds a Linux
SoC around the VexRiscv-SMP CPU (1 to 8 cores, FPU and RVC optional, coherent DMA) for the
boards of LiteX-Boards, with LiteDRAM, LiteEth, LiteSDCard, LiteSATA, PCIe, USB OHCI, the
framebuffer and the usual peripherals:

```sh
git clone https://github.com/litex-hub/linux-on-litex-vexriscv && cd linux-on-litex-vexriscv
./make.py --board=arty --build --load        # ./make.py --help lists the boards and the options
```

`--with-ethernet`, `--with-sdcard`, `--with-sata`, `--with-video-framebuffer`,
`--with-spi-flash`, `--cpu-count`, `--with-fpu` are the usual options. Xilinx, Intel, Lattice,
Microsemi, Efinix and Gowin boards are supported, and on Lattice ECP5 the whole stack, CPU,
cores and toolchain, is open source.

## 2. Get the images

Four files: OpenSBI, the kernel, the device tree and a Buildroot root filesystem, with the
`boot.json` that tells the BIOS where each one goes. Prebuilt ones are attached to
[issue #164](https://github.com/litex-hub/linux-on-litex-vexriscv/issues/164) of the project;
to build them yourself:

```sh
git clone https://github.com/buildroot/buildroot && cd buildroot
make BR2_EXTERNAL=../linux-on-litex-vexriscv/buildroot/ litex_vexriscv_defconfig
make                                        # output/images/: Image, rootfs.cpio, opensbi.bin, rv32.dtb
```

## 3. Boot it

```sh
litex_term /dev/ttyUSB1 --images=images/boot.json     # serial boot of the four images
```

Or copy them to a TFTP root or an SD card: the BIOS netboots or sdcardboots them in a few
seconds ([the boot methods](Write-Firmware-For-Your-SoC.md#4-load-it)). The BIOS loads the
four files, jumps to OpenSBI, OpenSBI starts the kernel, Buildroot gives you a login:

![Linux booting on a LiteX SoC](images/litex-linux-boot.svg)

*The BIOS, OpenSBI, the kernel, the login prompt: this one in Verilator (`./sim.py` of the
project), the board does the same faster.*

Et voilà! `root` logs in without a password.

![Linux on LiteX](https://user-images.githubusercontent.com/1450143/89118966-96567a00-d4aa-11ea-9827-999a8ffd1444.jpg)

## 4. The other CPUs

- **NaxRiscv, VexiiRiscv** (64-bit, the current SpinalHDL generation): the LiteX-Boards targets
  with `--cpu-type=naxriscv --xlen 64` or `--cpu-type=vexiiriscv --cpu-variant=linux` (or
  `debian`), the images from the CPUs' documentation (the SpinalHDL repositories describe the
  Linux and Debian builds), the BIOS boot as above.
- **Rocket** (64-bit, Chisel): [Linux-on-LiteX-Rocket](https://github.com/litex-hub/linux-on-litex-rocket),
  the `linux` and `full` variants, an upstream kernel in a BBL payload with a BusyBox
  initramfs, on ECP5 (Versa, TrellisBoard, ECPIX-5), Nexys Video and others; maintained by
  Gabriel Somlo, who also [self-hosts Fedora](https://www.contrib.andrew.cmu.edu/~somlo/BTCP/)
  on it.
- **CVA6, OpenC906, BlackParrot** (64-bit): their upstream Linux support; BlackParrot was
  demonstrated in [Linux-On-LiteX-BlackParrot](https://github.com/scanakci/linux-on-litex-blackparrot).
- **mor1kx, Marocchino** (OpenRISC): the `linux`, `linux+smp` and `linux+fpu` variants and the
  upstream OpenRISC kernel (`arch/openrisc/boot/dts/or1klitex.dts`); mor1kx was the first CPU
  to boot Linux on LiteX.
- **Microwatt** (POWER): upstream Linux has the Microwatt platform; in LiteX the integration is
  used with the BIOS and bare metal, the Linux flow of the
  [Microwatt project](https://github.com/antonblanchard/microwatt) uses LiteDRAM through its
  standalone generator.
- **The hard CPUs** (Zynq, ZynqMP, Cyclone V and Agilex HPS): the vendor Linux runs on the
  hard cores, the LiteX gateware is reached through the AXI bridges and the host tools through
  `litex_server --devmem` ([Hard core CPUs](Hard-core-CPUs.md)).

## 5. The device tree and the drivers

```sh
litex_json2dts_linux build/<board>/csr.json > soc.dts          # --initrd, --initrd-start/size, --root-device, --polling
dtc -O dtb -o soc.dtb soc.dts
```

`litex_json2dts_linux` writes the nodes of the CPUs, the interrupt controller, the memory,
the LiteUART, LiteEth, LiteSDCard, LiteSPI flash, the I2C controllers, the GPIOs, the
framebuffer and the SoC controller from the build's `csr.json`. The drivers are upstream in
the kernel (`drivers/tty/serial/liteuart.c`, `drivers/net/ethernet/litex/`,
`drivers/mmc/host/litex_mmc.c`, `drivers/soc/litex/litex_soc_ctrl.c`); the others (SPI
flash, GPIO, I2C, framebuffer) use generic drivers (`spi-bitbang`, `gpio-mmio`,
`simple-framebuffer`) or the Linux-on-LiteX-VexRiscv patches. [barebox](https://www.barebox.org/)
has a LiteX board and drivers, U-Boot the LiteEth driver.

[OpenSBI](https://github.com/litex-hub/opensbi) (the `*-linux-on-litex-vexriscv` branches
carry the LiteX platform) is the firmware between the BIOS and the kernel on RISC-V: the
BIOS loads `opensbi.bin`, the kernel, the device tree and the rootfs from `boot.json` and
jumps to OpenSBI.

## 6. Without a board

- `./sim.py` in Linux-on-LiteX-VexRiscv runs the same SoC in Verilator with the images
  preloaded: slow (minutes to the login prompt) but cycle accurate, and what the capture above
  shows. The QEMU co-simulation (`litex_sim --cpu-type=qemu --qemu-kernel=...`) boots Linux in
  seconds against the simulated peripherals.
- [Renode](SoC-Simulator.md#renode) simulates the SoC from `csr.json` with the Linux images,
  fast, with network.

## Beyond Linux-on-LiteX

[OpenWrt](https://github.com/enjoy-digital/litex_openwrt_test), [Debian](https://github.com/roryt12/RISCV64-Debian-Linux-on-FPGA-with-Litex)
(archived) and [Fedora](https://www.contrib.andrew.cmu.edu/~somlo/BTCP/) have been run on
LiteX SoCs; [Xous](https://github.com/betrusted-io/xous-core) (the Precursor microkernel) is
the largest non-Linux system on one. The LiteX-Boards targets with `--cpu-type=vexriscv_smp`
and the [complex SoC](Create-A-Complex-SoC.md) page show what the Linux SoC is made of.

## Next

- [Create a complex SoC](Create-A-Complex-SoC.md): the DRAM, Ethernet and storage the Linux SoC needs.
- [Choosing a CPU](Choosing-A-CPU.md): VexRiscv-SMP, NaxRiscv, VexiiRiscv, Rocket.
- [BIOS](BIOS.md): the boot sequence that loads the four images.
- [LiteX on the Acorn CLE 215+](Use-LiteX-on-the-Acorn-CLE-215.md): Linux with SATA and PCIe on a cheap card.
