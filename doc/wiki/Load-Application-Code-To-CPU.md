For SoCs with CPU(s), LiteX offers various approaches/methods to load and jump to application's code from the BIOS.

# ROM Boot:
Running the application code from a embedded ROM is the fastest way to execute code and could be interesting when the code is small enough or on large devices where many block-rams are available at almost no cost, or simply when the execution speed is critical. 

An boot ROM with contents from `bootrom.bin` file, located at `0x20000000` can be added to the SoC with:
```python3
self.add_rom("bootrom", 0x20000000, 2**10, contents=get_mem_data("bootrom.bin", endianness="little"))  # "little" for the default RISCV architectures selected by litex
```
Defining `ROM_BOOT_ADDRESS` in the SoC makes the BIOS jump to this address when the boot methods before it (serial, flash) did not boot. The BIOS tries the methods in this order: serial, flash, rom, sdcard, sata, net; the `<X>_BOOT_PRIORITY` and `<X>_BOOT_DISABLE` constants change or disable them ([BIOS](BIOS.md)):
```python3
self.add_constant("ROM_BOOT_ADDRESS", 0x20000000)
```

# Serial Boot:
Loading application code from serial is very convenient for development since provides an easy way
to (re)load application code, boot to it and do quick iterations. LiteX supports very various serial interfaces that can be configured for the board with:

`--uart-name=serial`: _Regular_ UART at 115200Bauds, ~10-15KB/s upload.

`--uart-name=serial --uart-baudrate=1000000`: _Boosted_ UART at 1MBauds, ~80-90KB/s upload.

`--uart-name=serial --uart-baudrate=3000000`: _Overboosted_ UART at 3MBauds :), ~250KB/s upload.

`--uart-name=usb_fifo`: UART through FT245 FIFO, ~300KB/s upload (boards with `usb_fifo` pads).

`--uart-name=usb_acm`: UART through the USB CDC-ACM core (LUNA, on a ULPI PHY or on LiteX's soft USB2 PHY), no USB-UART chip needed.

`--uart-name=jtag_uart`: UART through the JTAG TAP, no serial port needed (`litex_term jtag --jtag-config=openocd_xc7_ft2232.cfg`).

`--uart-name=etc... or create yours!`

Serial boot is generally slow compared to Ethernet or SDCard boot but is the easiest to setup and usable on all boards so is still very interesting for easy use or when no alternative are available.

LiteX's [litex_term](https://github.com/enjoy-digital/litex/blob/master/litex/tools/litex_term.py) tool is used to upload the application code and is directly installed with LiteX, available with the `litex_term` command.

Serial boot is the first boot method (priority 0) and the BIOS always tries it first (unless `SERIAL_BOOT_DISABLE` is defined). If `litex_term` is running on the Host, it upload the binary(ies) at startup: 
```bash
--============== Boot ==================--
Booting from serial...
Press Q or ESC to abort boot completely.
sL5DdSMmkekro
[LITEX-TERM] Received firmware download request from the device.
[LITEX-TERM] Uploading buildroot/Image to 0x40000000 (4545524 bytes)...
[LITEX-TERM] Upload complete (162.0KB/s).
[LITEX-TERM] Uploading buildroot/rv32.dtb to 0x40ef0000 (1995 bytes)...
[LITEX-TERM] Upload complete (191.2KB/s).
[LITEX-TERM] Uploading opensbi.bin to 0x40f00000 (53640 bytes)...
[LITEX-TERM] Upload complete (161.1KB/s).
[LITEX-TERM] Booting the device.
[LITEX-TERM] Done.
Executing booted program at 0x40f00000
--============= Liftoff! ===============--
...
```
Otherwise it will try the next available boot method, here for example the falling back to SDCard:
```bash
--============== Boot ==================--
Booting from serial...
Press Q or ESC to abort boot completely.
sL5DdSMmkekro
Timeout
Booting from SDCard in SPI-Mode...
...
```

 1. Uploading a single binary:

To load `boot.bin` to default location (`main_ram`, `0x40000000` on most SoCs, `--kernel-adr` to change it), start `litex_term` with:
```bash
litex_term /dev/ttyUSBX --kernel=boot.bin
```
 2. Uploading multiple binaries with a *JSON* description file:

When multiple binaries need to be loaded at different locations, a *JSON* description file with file/address tuples can be used, as for example the `boot.json` file used for [Linux-on-LiteX-VexRiscv](https://github.com/litex-hub/linux-on-litex-vexriscv):
```json
{
	"Image":        "0x40000000",
	"rv32.dtb":     "0x40ef0000",
	"opensbi.bin":  "0x40f00000"
}
```

The **last file/address tuple** is used for the CPU **jump** (so here it will jump to `0x40f00000`, OpenSBI).

It is also possible to optionally specify the `r1/r2/r3` and `addr` boot arguments:
```json
{
	"Image":        "0x40000000",
	"rv32.dtb":     "0x40ef0000",
	"opensbi.bin":  "0x40f00000",
	"bootargs": {
		"r1":   "0x00000000",
		"r2":   "0x00000000",
		"r3":   "0x00000000",
		"addr": "0x40f00000"
	}
}
```
In this case, instead of defaulting to `0`, `r1/r2/r3` will use the specified value and `addr` will be used for the CPU jump. `bootargs` is read by the BIOS for the TFTP, SD card and SATA boots; `litex_term --images` only loads the file/address pairs.

To use a _JSON_ file, start `litex_term` with:
```bash
litex_term /dev/ttyUSBX --images=boot.json
```
`litex_term --serial-boot` starts the upload without waiting for the BIOS prompt, `--safe` disables the upload speed optimizations (for unreliable links), `--kernel-adr` changes the load address. From the BIOS console, `serialboot`, `netboot [file]`, `flashboot`, `romboot`, `sdcardboot [file]` and `sataboot [file]` run one method again.

# Ethernet Boot:
On SoCs with Ethernet capability, loading application code with it can be very convenient for development since flexible  and fast (on a Linux SoC, loading binaries only takes a few seconds).

Ethernet boot requires a *TFTP* server on the Host. By default the SoC's IP address is `192.168.1.50` and the TFTP server (the Host) `192.168.1.100`; the targets expose `--eth-ip`, `--remote-ip` (and `--eth-dhcp` to get the SoC's address from DHCP), and the SoC can define the `REMOTEIPX` constants directly:
```python3
self.add_constant("REMOTEIP1", 192)
self.add_constant("REMOTEIP2", 168)
self.add_constant("REMOTEIP3", 1)
self.add_constant("REMOTEIP4", X)
```

 1. Uploading multiple binaries with a *JSON* description file:

The BIOS will first try to load a `boot.json` file over TFTP that will provide the list of files that need to be loaded and their location in the SoC, as for example the `boot.json` file used in [Linux-on-LiteX-VexRiscv](https://github.com/litex-hub/linux-on-litex-vexriscv)
```json
{
	"Image":        "0x40000000",
	"rv32.dtb":     "0x40ef0000",
	"opensbi.bin":  "0x40f00000"
}
```
2. Uploading a single binary:

When `boot.json` is not available on the TFTP (or when `boot.json` is invalid), the BIOS will fallback to `boot.bin`. So when only one binary is used, it could be simply named `boot.bin` and put on the TFTP, the BIOS will load it to the main RAM origin (`0x40000000` on most SoCs) and jump to it.

Example of Linux ethernet boot on [Arty A7](https://store.digilentinc.com/arty-a7-artix-7-fpga-development-board-for-makers-and-hobbyists/) board:
![enter image description here](https://web.archive.org/web/20221207075844im_/https://cdn10.bigcommerce.com/s-7gavg/product_images/attribute_rule_images/6425_zoom_1527801259.png)

```bash
--============== Boot ==================--
Booting from serial...
Press Q or ESC to abort boot completely.
sL5DdSMmkekro
Timeout
Booting from network...
Local IP : 192.168.1.50
Remote IP: 192.168.1.100
Booting from boot.json...
Copying Image to 0x40000000... (4545524 bytes)
Copying rootfs.cpio to 0x40800000... (8029184 bytes)
Copying rv32.dtb to 0x41000000... (2167 bytes)
Copying emulator.bin to 0x41100000... (9600 bytes)
Executing booted program at 0x40f00000

--============= Liftoff! ===============--
```

# SPIFlash Boot:
Most of the FPGA based systems are storing their bitstreams in SPIFlash. This SPIFlash is generally a lot larger than the FPGA bitstream size and thus allows storing software applications in the unused part.

To store an application in SPIFlash, the application first need to be prepared to add Length/CRC information to it:
```bash
python3 -m litex.soc.software.crcfbigen app.bin -o app.fbi --fbi --little
```

The `.fbi` file can then be flashed to a specific location of the SPIFlash.

Let's say SPIFlash is mapped at address `0x30000000` of the SoC and application has been flashed at address `0x40000` of the SPIFlash, defining `FLASH_BOOT_ADDRESS` in the SoC will make it jump to the defined value at startup:

```python3
self.add_constant("FLASH_BOOT_ADDRESS", 0x30040000)
```

# SDCard/SATA Boot:
Loading application code from SDCard/SATA is very interesting for standalone embedded systems and allow very large binaries. 

The BIOS supports loading files from FAT16/FAT32 partitions and boot scheme is similar to Ethernet boot:  File format is identical, BIOS will first  look for a valid `boot.json` file, will eventually fallback to `boot.bin` if `boot.json` is not available or not valid, and will fails if neither of these are found/valid.

![](https://pbs.twimg.com/media/EaPya68XgAEEKvB?format=png&name=small)

Example of Linux SDCard boot on the [OrangeCrab](https://groupgets.com/campaigns/710-orangecrab):
![OrangeCrab](https://raw.githubusercontent.com/gregdavill/OrangeCrab/main/documentation/hugo-files/static/docs/r0.2/orangeCrab-1.jpg)
[![asciicast](https://asciinema.org/a/cFQ7JRH96mgJNcuI0Ntey663H.svg)](https://asciinema.org/a/cFQ7JRH96mgJNcuI0Ntey663H)
