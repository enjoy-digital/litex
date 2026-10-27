# AXI Bus

[AXI](https://developer.arm.com/documentation/ihi0022/latest/) (Advanced eXtensible Interface,
from Arm's AMBA) is the bus of the vendor IPs, the hard CPUs (Zynq, Agilex and Cyclone V HPS)
and the high-performance soft CPUs (NaxRiscv, VexiiRiscv, Rocket, CVA6, OpenC906). LiteX
implements AXI4, AXI4-Lite and AXI4-Stream in `litex/soc/interconnect/axi/`, with the same
building blocks as Wishbone (interconnects, converters, bridges, SRAM, CDC, timeout), and a SoC
can use `--bus-standard=axi-lite` or `axi` for its main bus, or mix masters and slaves of
different standards: the [SoC builder](SoC-builder.md) inserts the bridges.

![AXI in LiteX](images/litex-axi.svg)

## The three flavours

| | Interface | Channels | Use |
| --- | --- | --- | --- |
| **AXI4-Lite** | `AXILiteInterface(data_width=32, address_width=32)` | `aw`, `w`, `b`, `ar`, `r` (no bursts, no IDs) | Control: CSRs and simple peripherals; the bus of vendor IP control ports; `--bus-standard=axi-lite`. |
| **AXI4** (full) | `AXIInterface(data_width, address_width, id_width=1, version="axi4"\|"axi3", bursting)` | The five channels with bursts (`len`, `size`, `burst`), IDs, responses | Memory traffic: DMAs, DRAM (LiteDRAM AXI port), the HPS bridges, the big CPUs; `--bus-standard=axi`. |
| **AXI4-Stream** | `AXIStreamInterface(data_width, keep_width, id_width, dest_width, user_width)` | One channel: `tvalid`/`tready`/`tlast`/`tdata`/`tkeep`/`tid`/`tdest`/`tuser` | Data paths: it is a LiteX [stream](Streams.md) endpoint (payload `data`/`keep`, params `id`/`dest`/`user`), so it connects to any stream directly. |

Every channel of an AXI interface is itself a stream endpoint (`axi.aw.valid`,
`axi.aw.addr`...), which is why the stream blocks (FIFOs, CDCs, pipelines) apply to AXI.
AXI addressing is always in bytes.

```python
from litex.soc.interconnect.axi import *

axi_lite = AXILiteInterface(data_width=32, address_width=32)
axi      = AXIInterface(data_width=128, address_width=32, id_width=4)
axis     = AXIStreamInterface(data_width=64, user_width=1)

# The ports of a Verilog AXI core: name them axi_*, LiteX connects them:
self.specials += Instance("my_axi_core", **axi.get_ios("s_axi"))         # or axi.connect_to_pads(pads, mode="slave")
```

## The building blocks

| AXI4-Lite (`axi_lite.py`) | AXI4 (`axi_full.py`) | Purpose |
| --- | --- | --- |
| `AXILiteInterconnectShared`, `AXILiteCrossbar`, `AXILiteInterconnectPointToPoint` | `AXIInterconnectShared`, `AXICrossbar`, `AXIInterconnectPointToPoint` | Interconnects (shared bus or crossbar, with `AXILiteArbiter`/`AXIArbiter` and `AXILiteDecoder`/`AXIDecoder`; the AXI arbiter can interleave transactions by ID). |
| `AXILiteSRAM` | `AXISRAM` | A block RAM on the bus. |
| `AXILiteConverter` (`AXILiteUpConverter`/`DownConverter`) | `AXIConverter` (`AXIUpConverter`/`DownConverter`), `AXIBurst2Beat` | Data width conversion; burst to single-beat conversion for simple slaves. |
| `AXILiteClockDomainCrossing`, `AXILiteTimeout` | `AXIClockDomainCrossing`, `AXITimeout` | Clock domain crossing, timeout. |
| `AXILiteRemapper`, `AXILiteOffset` | `AXIRemapper`, `AXIOffset` | Address remapping. |
| `AXILite2CSR` | | The bridge to the [CSR bus](CSR-Bus.md) (used when the main bus is AXI-Lite). |
| `AXILite2Wishbone`, `Wishbone2AXILite` | `AXI2Wishbone`, `Wishbone2AXI`, `AXI2AXILite`, `AXILite2AXI` | The bridges between standards (`axi_lite_to_wishbone.py`, `axi_full_to_wishbone.py`, `axi_full_to_axi_lite.py`). |

The SoC bus handler uses them automatically: a Wishbone CPU on an AXI main bus gets a
`Wishbone2AXI`, an AXI-Lite vendor IP on a Wishbone bus an `AXILite2Wishbone`, and widths are
converted on the way (`SoCBusHandler.add_adapter`). `--bus-low-latency` selects the
lower-latency bridges where available.

## Where AXI appears in a LiteX SoC

- **Vendor and hard IP**: Zynq-7000/ZynqMP PS ports, the Cyclone V and Agilex HPS bridges,
  Xilinx MIG and HBM2, Efinix DDR: LiteX adds them as AXI masters or slaves of the main bus.
- **CPUs**: NaxRiscv/VexiiRiscv (AXI-Lite peripheral bus, AXI memory and DMA buses), Rocket,
  CVA6, OpenC906, VeeR, Cortex-M, the MIPS cores.
- **LiteDRAM**: `LiteDRAMAXIPort`/`LiteDRAMAXI2Native` give AXI ports on the crossbar for the
  CPUs' memory buses and DMAs, with full bursts.
- **Standalone cores**: `litex_soc_gen --bus-standard=axi-lite` and the `*_gen` generators
  export the control bus as AXI-Lite and the data paths as AXI-Stream for integration in a
  Vivado/Quartus block design ([Export](Export-Your-Core-SoC-To-Verilog.md)).
- **Custom logic**: a core with an `AXILiteInterface` and `add_slave`, or a DMA with an
  `AXIInterface` and `add_master`, exactly as with [Wishbone](Wishbone-Bus.md).
