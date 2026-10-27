# Wishbone Bus

The [Wishbone](https://cdn.opencores.org/downloads/wbspec_b4.pdf) bus is the default
memory-mapped bus of LiteX SoCs: simple (one request/acknowledge handshake, no channels),
open, and what most soft CPUs and small cores speak. LiteX implements Wishbone *classic*
(standard handshaking, synchronous feedback) with optional incrementing bursts (`cti`/`bte`),
in `litex/soc/interconnect/wishbone.py`, and the SoC builder bridges it to AXI-Lite and AXI when
a master or a slave needs them ([AXI-Bus](AXI-Bus.md), [SoC-builder](SoC-builder.md)).

![Wishbone in a LiteX SoC](images/litex-buses.svg)

## The interface

| Signal | Direction | Role |
| --- | --- | --- |
| `adr` | master to slave | Address, in words by default (`addressing="word"`, 30 bits for a 32-bit bus) or in bytes (`addressing="byte"`). |
| `dat_w`, `dat_r` | master to slave, slave to master | Write and read data (`data_width`: 32 by default, 8 to 512). |
| `sel` | master to slave | Byte select, one bit per byte. |
| `cyc`, `stb` | master to slave | Cycle and strobe: a request is `cyc & stb`. |
| `we` | master to slave | Write enable. |
| `ack`, `err` | slave to master | Acknowledge (one per request) or error. |
| `cti`, `bte` | master to slave | Cycle type and burst type: `CTI_BURST_INCREMENTING`/`END` with `bursting=True`. |

```python
from litex.soc.interconnect import wishbone

bus = wishbone.Interface(data_width=32, address_width=32, addressing="word", bursting=False)
# In a simulation generator:
yield from bus.write(0x10, 0xdeadbeef)
value = yield from bus.read(0x10)
```

A transaction is one request (`cyc & stb`, with `we`, `adr`, `dat_w`, `sel`) answered by one
`ack` (or `err`); with bursting, consecutive words of an incrementing burst are acknowledged
one per cycle. There is no outstanding request: the master waits for the acknowledge. This is
what makes Wishbone small, and what limits its throughput against AXI for DMAs on wide
memories (LiteDRAM offers native and AXI ports for those).

## The building blocks

| Block | Purpose |
| --- | --- |
| `InterconnectShared(masters, slaves, register, timeout_cycles, arbiter)` | A shared bus: an `Arbiter` (round robin on `cyc`, `mode="cycle"` or `"transaction"`) and a `Decoder` (one slave per address range). The default of the SoC builder. |
| `Crossbar(masters, slaves, register)` | Every master reaches every slave at the same time (`--bus-interconnect=crossbar`). |
| `InterconnectPointToPoint(master, slave)` | A direct connection. |
| `Decoder(master, [(fn, bus), ...])`, `Arbiter(masters, target)` | The pieces, for custom topologies. |
| `SRAM(mem_or_size, read_only, init, bus)` | A memory on the bus (block RAM), with burst support. |
| `Converter`, `UpConverter`, `DownConverter` | Data width conversion (word addressing). |
| `Timeout(master, cycles)` | Acknowledges with an error after `cycles` without answer, so a missing slave does not hang the CPU (`--bus-timeout`). |
| `Cache(cachesize, master, slave)` | A write-back cache (the L2 in front of LiteDRAM: `--l2-size`). |
| `ClockDomainCrossing(master, slave, cd_from, cd_to)` | A crossing between two clock domains. |
| `Remapper`, `Offset` | Address remapping and offset for masters with their own view of the memory. |
| `Wishbone2CSR` | The bridge to the [CSR bus](CSR-Bus.md). |
| `Wishbone2AXILite`, `AXILite2Wishbone`, `Wishbone2AXI`, `AXI2Wishbone`, `Wishbone2AvalonMM`, `AvalonMM2Wishbone`, `AHB2Wishbone` | The bridges to the other standards (`litex/soc/interconnect/axi/`, `avalon/`, `ahb.py`). |

## In a SoC

The SoC builder owns the main bus (`self.bus`): masters (`self.bus.add_master`) and slaves
(`self.bus.add_slave` with a `SoCRegion`) are collected, adapted (data width, addressing,
standard) and connected at finalization by the interconnect, with the timeout. A core with a
Wishbone interface is added in one line:

```python
from litex.soc.interconnect import wishbone
from litex.soc.integration.soc import SoCRegion

class MyCore(LiteXModule):
    def __init__(self):
        self.bus = wishbone.Interface(data_width=32, address_width=32, addressing="word")
        self.mem = wishbone.SRAM(0x1000, bus=self.bus)      # or your own logic on self.bus

# In the SoC:
self.mycore = MyCore()
self.bus.add_slave("mycore", self.mycore.bus, SoCRegion(origin=0x90000000, size=0x1000, cached=False))
```

The CPU's instruction and data buses are the usual masters; the host [bridges](Host-Bridges.md)
and the DMAs are the others. `--bus-data-width=64` (or more) widens the main bus for a
64-bit CPU or a wide DRAM port, `--bus-bursting` enables the bursts, `--bus-addressing=byte`
makes the addressing match AXI's. The generated `mem.h` and `csr.csv` describe the resulting map.
