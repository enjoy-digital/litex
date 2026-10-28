The Acorn CLE 215+ is a cryptocurrency mining accelerator card from SQRL that can be
repurposed as a generic FPGA PCIe development board, and a cheap one: an afternoon with a
soldering iron for the adapters, then the usual LiteX commands.

<div>
<img src="https://user-images.githubusercontent.com/1450143/101366194-f0c27580-38a4-11eb-9d90-830d9c98dfec.png" width="400">
<img src="https://user-images.githubusercontent.com/1450143/101523904-85060880-3989-11eb-91ff-4bd50e9189cb.png" width="400">
</div>

It features:

 - An Artix7 XC7A200T speedgrade -3.
 - A 16-bit / 1 GiB DDR3.
 - A 32MiB QSPI Flash.
 - A PCIe Gen2 X4 M2 connector (exposing the 4 GTP transceivers! - up to 6.6 Gb/s)
 - 4 User leds.
 - A JTAG connector.
 - 4 General purpose IOs.
 - 4 LVDS pairs IOs.
 
 The Acorn CLE215+ is in fact the [NiteFury](https://github.com/RHSResearchLLC/NiteFury-and-LiteFury) board with more memory: 1GB instead of 512MB. Both NiteFury and LiteFury boards are really interesting boards, but what makes the Acorn CLE215+ even more interesting is that it's available for very cheap: from ~60 euros to 100 euros on eBay at the time we write this Wiki page... The boards can be found at these prices since no longer useful in  cryptocurrency mining... but still interesting for us as FPGA dev boards :)

## Prepare your Acorn CLE215+ for LiteX
![enter image description here](https://user-images.githubusercontent.com/1450143/101524205-ee861700-3989-11eb-9f17-b77a39ce4339.JPG)
To use the Acorn CLE215+ as a LiteX development board, the following hardware is recommended:
 - A PCIe 1X to 16X powered riser adapter card (ex [this one](https://www.amazon.fr/Mini%C3%A8re-renforc%C3%A9e-extension-Adaptateur-dalimentation/dp/B0721MG66S))
 - A M2 NVME to PCIe Gen2 X4 adapter card (ex [this one](https://www.amazon.fr/GLOTRENDS-PCIe-Adapter-2230-2280-PA05/dp/B079546NPR)).
 - A JTAG Cable (ex [this one](https://www.digikey.fr/fr/product-highlight/d/digilent/jtag-hs2-programming-cable)).
 - A USB to TTL serial cable (ex [this one](https://www.amazon.fr/gp/product/B081QKRHM3)).
 - A Molex PICOEZMATE 6 cable (ex [this one](https://www.digikey.fr/en/products/detail/molex/0369200601/10233018)).
- 2 X 6 pin headers.

An extra PCIe riser + SATA cable will be useful if you want to create SoCs with LiteSATA.

### Prepare the JTAG and Serial adapters
The Acorn exposes the JTAG pins and general purpose IOs to 6-pin Pico-EZmate connectors. We need to create adapters for both connectors. The JTAG will be used to program the FPGA and the second connector for IOs (UART in our case):

![enter image description here](https://user-images.githubusercontent.com/1450143/101597785-77876780-39f7-11eb-92a3-99b27e82e02b.png)

You can cut the Pico-EZmate cable in half and solder the pin-headers according to the pin mapping provided:

![enter image description here](https://user-images.githubusercontent.com/1450143/101526278-a61c2880-398c-11eb-9765-766ee42c0222.JPG)

You can now mount the cable adapters on the board and the board on the PCIe adapters:

![enter image description here](https://user-images.githubusercontent.com/1450143/101598489-8884a880-39f8-11eb-8bcc-280461db326d.JPG)
![enter image description here](https://user-images.githubusercontent.com/1450143/101598810-02b52d00-39f9-11eb-93bb-ede1a8e1a327.JPG)

If not already done, make sure to install LiteX by following the [LiteX installation guide](Installation.md) and you are ready to use LiteX your board!

## Make a SATA Adapter (optional)

You can make a SATA adapter from a spare PCIe X1 to USB3 connector (from a PCIe riser kit) and a SATA cable as demonstrated recently:

<a href="https://twitter.com/enjoy_digital/status/1320747775626272769" rel="SATA Adapter">![SATA Adapter](https://user-images.githubusercontent.com/1450143/101599464-157c3180-39fa-11eb-8334-d15985037a26.png)</a>

To create the SATA adapter, cut a SATA cable in half and solder it to the PCIe X1 using the following pinout:
![SATA Adapter](https://user-images.githubusercontent.com/1450143/101604586-6b080c80-3a01-11eb-8e15-701d74a4ce73.png)

This adapter will allow you to use LiteSATA on FPGA boards with a PCIe connector through a PCIe riser and USB3 cable. P/N polarity will automatically be detected/corrected by LiteSATA, so is not important when building the adapter.

## Run LiteX-Boards example

You are now ready to use LiteX on your board, let's first run a classical LiteX SoC on the board:

    python3 -m litex_boards.targets.sqrl_acorn --build --load

This will build a LiteX SoC with CPU/ROM/SRAM/DDR3 and load if to the board. At the end of the build you should see the LiteX BIOS prompt and be able to interact with it.

You can explore the [LiteX wiki](Home.md) or [LiteX-Boards](https://github.com/litex-hub/litex-boards) to discover what can already be done and play with it.

## Run Linux-on-LiteX-VexRiscv example

Now let's try to run Linux on the board using [Linux-on-LiteX-VexRiscv](https://github.com/litex-hub/linux-on-litex-vexriscv) project as demonstrated here:
<a href="https://twitter.com/enjoy_digital/status/1329744466907979778" rel="Linux">
![Linux](https://user-images.githubusercontent.com/1450143/101605994-267d7080-3a03-11eb-8995-6975b894225d.png)</a>

The SoC we are going to build is very similar to the previous one, but uses a different variant of the VexRiscv CPU (with a MMU) and also integrate the LiteSATA core to allow booting from SATA and storing the Linux file system to a SATA drive:

![enter image description here](https://user-images.githubusercontent.com/1450143/101606992-5711da00-3a04-11eb-9de6-3648720e2c9c.png)

To build the SoC, first get the Linux-on-LiteX-VexRiscv project:

    git clone https://github.com/litex-hub/linux-on-litex-vexriscv
    
And build the Acorn CLE215+ target:

    python3 make.py --board=acorn --build --load

You can then load the Linux images to the board over UART with:

    litex_term jtag --jtag-config=openocd_xc7_ft2232.cfg --images=images/boot.json

(The `acorn` board of Linux-on-LiteX-VexRiscv has no serial port and uses the JTAG UART; with the [LiteX Acorn Baseboard](https://github.com/enjoy-digital/litex-acorn-baseboard), `--board=acorn_baseboard_mini` has a real UART: `litex_term /dev/ttyUSBX --images=images/boot.json`.)

And you should see linux booting:

![enter image description here](https://user-images.githubusercontent.com/1450143/101607488-f636d180-3a04-11eb-9002-2d6ee301a1ff.jpeg)

Since the SoC integrates LiteSATA, it's also possible to boot over SATA with the optional SATA adapter, you can copy the Linux images directly to the SATA drive by following [this guide](Write-Firmware-For-Your-SoC.md#sd-card-and-sata), plug the SATA drive and should see the system booting directly from SATA.

## Acorn Giveaway
![https://user-images.githubusercontent.com/1450143/144005083-9dc62efa-a875-4abd-a3f5-4129e34267d2.png](https://user-images.githubusercontent.com/1450143/144005083-9dc62efa-a875-4abd-a3f5-4129e34267d2.png)

You received your Acorn from the [giveway](https://twitter.com/enjoy_digital/status/1461353848388284422) and/or want to reproduce the results on your Acorn? Please use the following instructions.

In the demo, a [Linux-on-LiteX-VexRiscv](https://github.com/litex-hub/linux-on-litex-vexriscv) design is flashed on the Acorn:
![enter image description here](https://user-images.githubusercontent.com/1450143/144007475-fc77e884-0a5e-4d28-be42-29b6b550abe4.png)

The design has been initially generated and over JTAG with:

    ./make.py --board=acorn_pcie --build --flash

The Linux driver is then available at `build/acorn_pcie/driver` and can be loaded with:

    cd build/acorn_pcie/driver/kernel
    make
    sudo ./init.sh

A `/dev/ttyLXU0` UART is created and can be used with LiteX-Term:

    litex_term /dev/ttyLXU0

And to load the Linux images:

    litex_term /dev/ttyLXU0 --images=images/boot.json

**FPGA bitstream update over PCIe:**

The Acorns are flashed with a Multiboot bitstream composed of a Fallback bitstream and Operational bitstream:

![enter image description here](https://user-images.githubusercontent.com/1450143/144006990-730a81bf-aedb-4310-a11a-f9dd97315cc3.png)
Updating the Operational bitstream over PCIe is possible with:

    cd build/acorn_pcie/driver/user
    make
    ./litepcie_util flash_write acorn_pcie_operational.bin 0x400000

A `./litepcie_util flash_reload` will reload the bitstream from SPI Flash and a PCIe rescan or reboot the computer will allow you to use the new bitstream.

> Note: Be careful of the **0x400000 offset** to only update the Operational bitstream.

## PCIe

Want PCIe instead of SATA? The GTPs are shared, so it's one or the other, and the target builds a PCIe Gen2 X4 SoC with LitePCIe, its Linux driver and user tools:

    python3 -m litex_boards.targets.sqrl_acorn --uart-name=crossover --with-pcie --driver --build --load
    cd build/sqrl_acorn/driver/kernel && make && sudo ./init.sh      # the LitePCIe kernel module (and /dev/ttyLXU0 for the crossover UART)
    cd ../user && make
    ./litepcie_util info                                             # the SoC identifier and the PCIe link
    ./litepcie_util scratch_test
    ./litepcie_util dma_test                                         # DMA loopback bandwidth

`--pcie-ndmas`, `--pcie-address-width` and `--pcie-with-dma-status`/`--pcie-with-dma-monitor` configure the DMAs, and the host can also reach the SoC bus through the BAR without the driver (`litex_server --pcie --pcie-bar=<id>`, see [Host-Bridges](Host-Bridges.md)). If you want more around the Acorn (a serial port, Ethernet, SFP cages, HDMI, SD card...), have a look at our [LiteX Acorn Baseboard](https://github.com/enjoy-digital/litex-acorn-baseboard) and its Mini version: `litex_boards.targets.litex_acorn_baseboard` and `litex_acorn_baseboard_mini` :)

## Going Further...

In this guide, we demonstrated a classical LiteX SoC with a CPU/ROM/RAM/DDR3 on the Acorn CLE 215+. The design is only using a fraction of the FPGA and leaves plenty of room for the user, so it already makes it a very nice and cheap FPGA development board. The NiteFury and LiteFury boards (and the Acorn CLE-101) can also be used: `--variant=cle-101` or `--variant=cle-215` select them (`cle-215+` is the default).

The board also exposes 4 GTP transceivers on the M2 connector which makes it very interesting to explore high speed serial links. We already demonstrated LiteSATA operation over a GTP (with 3 of them still available for user...), but it's also possible to build a Gen2 X4 PCIe design with LitePCIe on this board by following instructions in the LiteX-Boards [target](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/targets/sqrl_acorn.py) or explore low level layers of high speed serial links with LiteICLink [bench design](https://github.com/enjoy-digital/liteiclink/blob/master/bench/serdes/sqrl_acorn.py), etc...

A quad-core VexRiscv-SMP with DDR3 / PCIe Gen2 X4 has also been demonstrated on this board and is available in Linux-on-LiteX-VexRiscv (`--board=acorn_pcie`):
<a href="https://twitter.com/enjoy_digital/status/1257985111469015040" rel="VexRiscv-SMP">
![VexRiscv-SMP](https://user-images.githubusercontent.com/1450143/101612799-592b6700-3a0b-11eb-9d3f-94f255cae8f7.png)</a>

Boards with very similar capabilities are already supported by the open-source 7-Series flows ([F4PGA](https://f4pga.org/) and [openXC7](https://github.com/openXC7), `--toolchain=openxc7`; the Arty for example, which is lacking GTPs), so building these designs with a full open-source toolchain is getting closer!

Pretty exciting to see what can now be done with open-source hardware and less than 100$/€ nowadays no ? :)

## Next

- [Create a PCIe SoC](Create-A-PCIe-SoC.md): what `--with-pcie` builds on this board.
- [Run Linux on your SoC](Run-Linux-On-Your-SoC.md): the Linux-on-LiteX-VexRiscv flow in general.
- [Load and flash](Load-And-Flash.md): JTAG and the multiboot flash.
- [Projects](Projects.md): the Acorn baseboards and the other things built around this card.
