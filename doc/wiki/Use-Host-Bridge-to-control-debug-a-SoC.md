Being able to easily read/write the addressable space of the SoC from a Host PC with simple scripts can be very powerful and greatly help/speed up debugging.

<p align="center"><img src="https://user-images.githubusercontent.com/1450143/100260325-90990e80-2f49-11eb-8f6d-c485940b7d9e.png"></p>

# Add a UARTBone bridge to your SoC serial console:
The easiest way to add a UARTBone bridge to a SoC is to add it to the existing serial port. For example with digilent_arty:
```console
$ python3 -m litex_boards.targets.digilent_arty --uart-name=crossover+uartbone --build --load --csr-csv csr.csv
```

Once your bitstream is built and loaded to the board, start *litex_server* in UART mode:
```console
$ litex_server --uart --uart-port=/dev/ttyUSB0
```

Console communication to the board is still available as follows (assumes a csr file for the board named `csr.csv` is in the current directory):
```console
$ litex_term crossover
```
Alternately, for a csr file with a different name:
```console
$ litex_term crossover --csr-csv path/to/board_csr.csv
```

# Add a UARTBone bridge to your SoC:
Another easy way to add a UARTBone bridge to a SoC is to use an unused UART of your FPGA board. If your platform file already has a an unused UART you can just use it, otherwise you can simply add UART pins to your Platform file by adapting the following template:
```python3
   ("serial_debug", 0,
        Subsignal("tx", Pins("XY")),
        Subsignal("rx", Pins("YX")),
        IOStandard("LVCMOSXY")
    ),
```
and connect a USB/UART dongle between your FPGA board and your Host PC.

In your SoC, add the UARTBone bridge:
```python3
self.add_uartbone(uart_name="serial_debug", baudrate=115200)
```
and generate the *.csv* file that will be used by the tools:
```python3
builder  = Builder(soc, ..., csr_csv="csr.csv")
```

Once your bitstream is built and loaded to the board, start *litex_server* in UART mode:
```console
$ litex_server --uart --uart-port=/dev/ttyUSBX
```

# Add a JTAG bridge to your SoC:

On boards with limited IOs or simply to avoid a specific debug cable, using the JTAG bridge can be very convenient:

In your SoC, instantiate the JTAG bridge:
```python3
self.add_jtagbone()
```
and generate the *.csv* file that will be used by the tools:
```python3
builder  = Builder(soc, ..., csr_csv="csr.csv")
```
Once your bitstream is built and loaded to the board, start *litex_server* in JTAG mode:
```console
$ litex_server --jtag
```
Tadaaa! Here is your JTAG-to-AXI equivalent :)

# Add an Ethernet bridge to your SoC:
Another very convenient way to debug a SoC is to add an Ethernet Bridge to it this allows debugging your SoC over your local ethernet network and provide better speeds.

If your Platform file already has a an unused Ethernet PHY you can just use it, otherwise you can simply add the Ethernet pins to your Platform file by adapting the following template (here for a RMII PHY):
```python3
    ("eth_clocks", 0,
        Subsignal("ref_clk", Pins("X")),
        IOStandard("LVCMOS33"),
    ),

    ("eth", 0,
        Subsignal("rst_n", Pins("X")),
        Subsignal("rx_data", Pins("X X")),
        Subsignal("crs_dv", Pins("X")),
        Subsignal("tx_en", Pins("X")),
        Subsignal("tx_data", Pins("X X")),
        Subsignal("mdc", Pins("X")),
        Subsignal("mdio", Pins("X")),
        Subsignal("rx_er", Pins("X")),
        Subsignal("int_n", Pins("X")),
        IOStandard("LVCMOS33")
     ),
```
For the other types of Ethernet PHYs, you can find some inspiration in [LiteX-Boards](https://github.com/litex-hub/litex-boards/tree/master/litex_boards/platforms).

In your SoC, instantiate the Etherbone bridge:

```python3
from liteeth.phy import LiteEthPHYRMII      # or LiteEthPHYMII, LiteEthPHYRGMII, ...
self.ethphy = LiteEthPHYRMII(
    clock_pads = self.platform.request("eth_clocks"),
    pads       = self.platform.request("eth"))
self.add_etherbone(
    phy         = self.ethphy,
    ip_address  = "192.168.1.50",
    mac_address = 0x10e2d5000001
)
```

(Most LiteX-Boards targets do it for you with `--with-etherbone --eth-ip=192.168.1.50`, and `--with-ethernet --with-etherbone` shares the PHY between the CPU and the bridge.) The Builder always writes the `csr.csv` the tools need in the output directory (`build/<board>/csr.csv`, `--csr-csv` to choose the path).

Once your bitstream is built and loaded to the board, start _litex_server_ in UDP mode:

```console
$ litex_server --udp --udp-ip=192.168.1.50
```

If you want scan your network for available Etherbone/UDP devices, you can just do:

```console
$litex_server --udp --udp-scan --udp-ip=192.168.1.x --udp-port=1234
Etherbone scan on 192.168.1.x network:
- 192.168.1.20
- 192.168.1.50
```

# Add a PCIe bridge to your SoC:
On PCIe SoCs, the PCIe bridge is already present in the SoC since used to access the memory map of the SoC from the Host through the BAR0: `self.add_pcie(phy=self.pcie_phy, ...)` (the `--with-pcie` option of the targets) adds the `pcie_mmap` bus master (a `LitePCIeWishboneMaster`) along with the DMAs and the interrupts.

The bridge does not need the LitePCIe kernel driver: `litex_server` maps the BAR of the device through sysfs. The `csr.csv` of the build (`build/<board>/csr.csv`) is the one the tools use.

Then with *lspci*, find the location of the PCIe board on the bus, here `02:00.0`:
```
00:00.0 Host bridge: Intel Corporation Xeon E3-1200 v6/7th Gen Core Processor Host Bridge/DRAM Registers (rev 05)
[...]
00:1f.6 Ethernet controller: Intel Corporation Ethernet Connection (2) I219-V
02:00.0 Memory controller: Xilinx Corporation Device 7024
```
And use this to start _litex_server_ in PCIe mode:
```console
$ litex_server --pcie --pcie-bar=02:00.0
```

# Use LiteX's cli:

A simple [litex_cli](https://github.com/enjoy-digital/litex/blob/master/litex/tools/litex_client.py) comes with LiteX and can be used for simple and common operations: verify the bridge operation, read the identifier, read all or some registers of the SoC:

```
$ litex_cli --help
usage: litex_cli [-h] [--csr-csv CSR_CSV] [--host HOST] [--port PORT]
                 [--binary] [--file FILE] [--endianness {little,big}]
                 [--timeout TIMEOUT] [--strict-timeout] [--ident] [--regs]
                 [--filter FILTER] [--read READ] [--write [WRITE ...]]
                 [--length LENGTH] [--gui]

LiteX Client utility.

options:
  -h, --help            show this help message and exit
  --csr-csv CSR_CSV     CSR configuration file (default: csr.csv)
  --host HOST           Host ip address (default: localhost)
  --port PORT           Host bind port. (default: 1234)
  --binary              Use binary format for displayed values. (default: False)
  --file FILE           File to read from or write to in binary mode. (default: None)
  --endianness {little,big}
                        Endianness for memory accesses (little or big). (default: little)
  --timeout TIMEOUT     Socket timeout. (default: 2.0)
  --strict-timeout      Raise on remote read timeout. (default: False)
  --ident               Dump SoC identifier. (default: False)
  --regs                Dump SoC registers. (default: False)
  --filter FILTER       Registers filter (to be used with --regs). (default: None)
  --read READ           Do a MMAP Read to SoC bus (--read addr/reg). (default: None)
  --write [WRITE ...]   Do a MMAP Write to SoC bus (--write addr/reg [data]). (default: None)
  --length LENGTH       MMAP access length. (default: 4)
  --gui                 Run GUI. (default: False)
```

```litex_cli --ident``` reads the SoC identifier, ```litex_cli --regs``` dumps all the registers of the SoC (`--filter leds` for some of them), ```litex_cli --read 0x40000000 --length 64``` and ```litex_cli --write leds_out 0x5``` access the bus (an address or a register name), ```litex_cli --gui``` opens a registers/memory viewer.

_Note:_ `litex_cli` reads `csr.csv` from the current directory by default; pass `--csr-csv build/<board>/csr.csv` from anywhere else.

# Create scripts to communicate from the Host PC with the bridge:

You can now easily create scripts to read/write from/to the main bus of your SoC:
```python3
#!/usr/bin/env python3

from litex import RemoteClient

bus = RemoteClient()
bus.open()

# # #

# Access SDRAM
bus.write(0x40000000, 0x12345678)
value = bus.read(0x40000000)

# Access SDRAM (with bus.mems and base address)
bus.write(bus.mems.main_ram.base, 0x12345678)
value = bus.read(bus.mems.main_ram.base)

# Trigger a reset of the SoC
bus.regs.ctrl_reset.write(1)
 
# Dump all CSR registers of the SoC
for name, reg in bus.regs.__dict__.items():
    print("0x{:08x} : 0x{:08x} {}".format(reg.addr, reg.read(), name))

[...]

# # #

bus.close()
```
