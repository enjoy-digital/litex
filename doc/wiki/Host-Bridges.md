A host bridge is a bus master in the gateware driven from the host PC: through it, the host
reads and writes the whole address space of the running SoC (CSRs, memories, cores) without
any CPU involved. It is how a board is brought up, how designs are debugged and measured
([LiteScope](Use-LiteScope-To-Debug-A-SoC.md)) and how many LiteX systems are controlled in
production (a Python script on the host and no firmware at all). The same host API works over
every transport: serial port, JTAG, Ethernet, PCIe, USB, or the AXI bridge of a hard CPU.

![LiteX host bridges](images/litex-host-bridges.svg)

The step by step page is [Use Host Bridge to control/debug a SoC](Use-Host-Bridge-to-control-debug-a-SoC.md);
this page describes the pieces.

## The bridges (gateware)

| Bridge | How to add it | Transport | Notes |
| --- | --- | --- | --- |
| **UARTBone** | `soc.add_uartbone()`, `--with-uartbone`, or `--uart-name=crossover+uartbone` (console and bridge on the same serial port) | serial port | `Stream2Wishbone` turns the byte stream into a Wishbone master (`litex/soc/cores/uart.py`). Simple and universal; the speed is the baudrate (use 1 to 3 Mbaud when the USB-UART allows it). |
| **JTAGBone** | `soc.add_jtagbone(chain=1)`, `--with-jtagbone` | the FPGA's JTAG port, through OpenOCD | A `JTAGPHY` on the vendor TAP (Xilinx BSCANE2/BSCAN_SPARTAN6, Lattice ECP5 JTAGG, Intel, Gowin, Efinix) plus the UARTBone protocol: no pins needed. `litex_server --jtag --jtag-config=<openocd cfg>`. |
| **Etherbone** | `soc.add_etherbone(phy=..., ip_address="192.168.1.50", mac_address=..., udp_port=1234)` (with LiteEth, `--with-etherbone` on most targets) | UDP over Ethernet | The [Etherbone](https://ohwr.org/project/etherbone-core) protocol: Wishbone records in UDP packets. Fast and routable; can share the MAC with the CPU's Ethernet (`with_ethmac`). `litex_server --udp --udp-ip=192.168.1.50`. |
| **PCIe** | LitePCIe `LitePCIeWishboneMaster` (`add_pcie` with the MMAP option) | PCIe | The host maps the BAR of the device (`/sys/bus/pci/devices/<id>/resource0`): `litex_server --pcie --pcie-bar=<id>`. The fastest path, also used by LitePCIe's own tools. |
| **USB** | a USB device answering the vendor control requests of `litex/tools/remote/comm_usb.py` on its control endpoint (a protocol inherited from the Fomu; LiteX has no device core for it today, its USB path being the LUNA CDC-ACM console, `--uart-name=usb_acm`) | USB | 32-bit accesses: `litex_server --usb --usb-vid=... --usb-pid=...`. |
| **DevMem** | the AXI bridge of a hard CPU (Zynq, Cyclone V HPS, Agilex HPS) | `/dev/mem` on the Linux running on the hard CPU | `litex_server --devmem --devmem-base=0xff200000` (Cyclone V HPS lightweight bridge; Zynq GP0 is at `0x40000000`). |

A design can have several bridges (UARTBone for bring-up, Etherbone for speed): each one is a
bus master arbitrated with the CPU and the DMAs ([SoC-builder](SoC-builder.md)).

## litex_server

`litex_server` is the process that owns the transport and serves the clients: it speaks the
Etherbone protocol over TCP (port 1234 by default, several clients at once, hardware accesses
serialized), so client scripts never deal with the transport.

```sh
litex_server --uart --uart-port=/dev/ttyUSB0 [--uart-baudrate=115200]
litex_server --jtag --jtag-config=openocd_xc7_ft232.cfg [--jtag-chain=1]
litex_server --udp --udp-ip=192.168.1.50 [--udp-port=1234]      # --udp-scan lists the devices on the network
litex_server --pcie --pcie-bar=0000:01:00.0
litex_server --usb --usb-vid=0x1209 --usb-pid=0x5bf0
litex_server --devmem --devmem-base=0xff200000 --devmem-size=0x200000
```

`--bind-ip`/`--bind-port` change where it listens (to reach a board from another machine),
`--debug` prints every access. The OpenOCD configuration files for `--jtag` are in
`litex/build/openocd/` (`openocd_xc7_ft232.cfg`, `openocd_xc7_ft2232.cfg`, `openocd_xc7_digilent.cfg`, ...).

## The client side

**Python scripts** use `RemoteClient` (`from litex import RemoteClient`), which reads `csr.csv`
(from the current directory, or `csr_csv=`) to know the registers and memory map:

```python
from litex import RemoteClient

bus = RemoteClient()                 # host="localhost", port=1234, csr_csv="csr.csv"
bus.open()

print(f"{bus.regs.ctrl_scratch.read():08x}")        # a CSR of the SoC controller
bus.regs.leds_out.write(0b0101)                       # a CSR of your core: <core>_<register>
data = bus.read(bus.mems.main_ram.base, 16)           # 16 words from main RAM
bus.write(bus.mems.main_ram.base, [0xdeadbeef])       # one word
print(bus.constants.config_clock_frequency)           # the SoC constants

bus.close()
```

`regs.<core>_<register>` has `.read()`/`.write()`, `mems.<region>` has `.base`/`.size`/`.type`,
`constants.<name>` the values of `soc.add_constant()`. Reads and writes of several words are
sent as bursts (up to 255 words with UARTBone). Register names are the ones of `csr.csv`,
i.e. `<module>_<csr>` with the module path flattened.

**litex_cli** does the common things from the shell:

```sh
litex_cli --ident                       # the SoC identifier
litex_cli --regs [--filter=leds]        # dump the registers
litex_cli --read 0x40000000 --length 64 # read memory (address or register name)
litex_cli --write leds_out 0x5
litex_cli --gui                         # registers, LEDs, buttons, XADC plots, memory viewer
```

**Through the bridge, without a serial port:** `--uart-name=crossover` gives the CPU a UART
whose other end is a set of CSRs: `litex_term crossover` connects to it through `litex_server`
(the BIOS console over JTAG or Ethernet). `--uart-name=jtag_uart` is the same idea directly on
the JTAG TAP (`litex_term jtag --jtag-config=...`). With `--with-cpu-jtag-debug
--cpu-jtag-debug-transport=csr`, `litex_jtag` exposes the CPU's debug TAP to OpenOCD through
`litex_server` (an OpenOCD `remote_bitbang` server), so GDB works over any bridge
([JTAG/GDB debugging](JTAG-GDB-Debugging-with-VexRiscv-SMP-NaxRiscv-VexiiRiscv-CPUs.md)).

[LiteScope](Use-LiteScope-To-Debug-A-SoC.md) uses the same client: `litescope_cli` and
`LiteScopeAnalyzerDriver(bus.regs, "analyzer")` configure the triggers, run the capture and
upload the samples through `litex_server`.

## Protocols

- **UARTBone** (`litex/tools/remote/comm_uart.py`, `Stream2Wishbone`): a command byte (`0x01`
  write burst incrementing, `0x02` read burst incrementing, `0x03`/`0x04` fixed-address
  bursts), a length byte (1 to 255 words), the address (4 bytes by default, 8 with
  `--addr-width=64`, MSB first), then the data words (MSB first); the gateware FSM resets
  after 100 ms without a complete command. JTAGBone carries the same bytes over the JTAG TAP.
- **Etherbone** (`litex/tools/remote/etherbone.py`): Etherbone packets with read/write
  records, over UDP between `litex_server` and the FPGA, and over TCP between the clients and
  `litex_server`.
- **PCIe, USB, DevMem**: plain 32-bit memory-mapped accesses.

The transports are in `litex/tools/remote/` (`comm_uart.py`, `comm_udp.py`, `comm_pcie.py`,
`comm_usb.py`, `comm_devmem.py`), one class each with `read(addr, length)`/`write(addr, datas)`:
a new transport is one file.
