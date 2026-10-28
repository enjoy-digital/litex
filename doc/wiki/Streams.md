LiteX's streams are the data-path interface of the framework: every core that moves data
(Ethernet, PCIe DMA, SD card, video, SerDes, converters, FIFOs) has stream *endpoints*, and
they connect to each other with one line. A stream is a group of signals (a Migen `Record`)
that is a simplified compromise between AXI-Stream and Avalon-ST:

| Signal | Direction | Role |
| --- | --- | --- |
| `valid` | source to sink | A word is present (like AXI-Stream `tvalid`). |
| `ready` | sink to source | The sink accepts it (like `tready`); a transfer happens on each cycle with `valid & ready`. |
| `first` | source to sink | First word of a packet (like Avalon-ST `sop`: it is often convenient to know the start of a packet directly instead of deducing it from `last`). Used for packets only. |
| `last` | source to sink | Last word of a packet (like `tlast`). Used for packets only. |
| `payload` | source to sink | A `Record` with its own layout (like `tdata`), new on each transfer: `data`, and for example `be` or `error`. |
| `param` | source to sink | An optional `Record` (like `tuser`) that can change at each start of packet: `length`, `ip_address`, `port`... |

![LiteX streams](images/litex-streams.svg)

```python
from litex.soc.interconnect import stream

layout = [("data", 32), ("be", 4)]                 # the payload: a 32-bit word with its byte enables
sink   = stream.Endpoint(layout)                   # an Endpoint has valid/ready/first/last + the payload
source = stream.Endpoint(stream.EndpointDescription(payload_layout=layout, param_layout=[("length", 16)]))

self.comb += source.connect(sink)                  # one line: every signal in the right direction
self.comb += source.connect(sink, omit={"be"})     # or only part of it (keep={...} / omit={...})
sink.data                                          # payload and param fields are reached directly
```

A module exposes `self.sink` (what it consumes) and `self.source` (what it produces); payload
and param fields are reached directly (`ep.data`). `first`/`last`/`payload`/`param` are
`reset_less`. The byte-enable convention (`be`, one bit per data byte, `last` independent of
the mask, header-only packets as a beat with `be=0`) is described in
[stream_byte_enables.md](https://github.com/enjoy-digital/litex/blob/master/doc/stream_byte_enables.md).

## The generic blocks (`litex/soc/interconnect/stream.py`)

| Block | Purpose |
| --- | --- |
| `SyncFIFO(layout, depth, buffered=False)`, `AsyncFIFO(layout, depth=4)` | FIFOs (synchronous, or between two clock domains `write`/`read`). |
| `ClockDomainCrossing(layout, cd_from, cd_to, depth, buffered)` | A clock domain crossing: an `AsyncFIFO` between the domains, a passthrough when they are the same. |
| `Buffer(layout, pipe_valid=True, pipe_ready=False)`, `PipeValid`, `PipeReady`, `Delay(layout, n)` | Register stages to break the timing paths (valid/payload, ready, or both). |
| `Converter(nbits_from, nbits_to, reverse=False)`, `StrideConverter(description_from, description_to)` | Width converters by integer ratio, on a data width or on a full layout (keeps `first`/`last`/`be`). |
| `Gearbox(i_dw, o_dw, msb_first=True)` | Width converter for non-integer ratios (SerDes gearboxes). |
| `Multiplexer(layout, n)`, `Demultiplexer(layout, n)`, `Crossbar(layout, n)` | Select one of `n` sources/sinks with a `sel` signal (`with_csr=True` for a register). |
| `Gate(layout)`, `Shifter(dw)`, `Cast(layout_from, layout_to)` | Enable/disable a stream, shift it, reinterpret its fields. |
| `Pack(layout_from, n)`, `Unpack(n, layout_to)` | Pack `n` words into one record and back. |
| `Monitor(endpoint, count_width, with_tokens, with_overflows, with_packets...)` | CSR counters of tokens, overflows, underflows, packets on an endpoint (debug, statistics). |
| `Pipeline(*modules)` | Chains modules `source -> sink` in order (also accepts bare endpoints); `.add()` appends. |
| `BufferizeEndpoints({name: DIR_SINK/DIR_SOURCE})` | A module transformer that buffers the listed endpoints of a module. |

```python
self.submodules.pipeline = stream.Pipeline(
    self.phy,                                    # source: 8-bit bytes from the PHY
    stream.Converter(8, 32),                     # 8 to 32 bits
    stream.SyncFIFO([("data", 32)], 64),         # a 64-word FIFO
    stream.ClockDomainCrossing([("data", 32)], cd_from="rx", cd_to="sys"),
    self.dma.sink,                               # sink: the DMA writing to memory
)
```

## Packets (`packet.py`)

`Packetizer` and `Depacketizer` insert and remove a header described by a `Header({"field": HeaderField(byte, offset, width)}, length)`
in front of the payload, with the byte shifts when the header length is not a multiple of the
data width; `PacketFIFO(layout, payload_depth, param_depth)` stores packets with their
parameters. LiteEth's MAC, ARP, IP, UDP and Etherbone layers, LitePCIe's TLP layer and
LiteSATA's link layer are stacks of these.

## AXI-Stream and Avalon-ST

- `AXIStreamInterface(data_width, keep_width, id_width, dest_width, user_width)`
  (`litex/soc/interconnect/axi/axi_stream.py`) is a stream `Endpoint` whose payload is
  `data`/`keep` and whose params are `id`/`dest`/`user`: it connects to a LiteX stream
  directly, and `get_ios()`/`connect_to_pads()` give the `t*` ports for a Verilog boundary
  (the standalone cores export AXI-Stream this way).
- `Native2AvalonST` and `AvalonST2Native` (`litex/soc/interconnect/avalon/avalon_st.py`)
  handle the ready latency of Avalon-ST.

## Simulation

The Migen simulator is enough for most stream modules: drive `valid`/`payload` and sample
`ready` from a generator, or use the Python models of the cores (`test/` in every
repository); `stream.Monitor` gives counters on hardware and LiteScope captures an endpoint
with its handshake.

[alanvgreen](https://github.com/alanvgreen) wrote a [thorough description of LiteX streams with a diagram](https://github.com/amaranth-lang/amaranth/issues/317#issuecomment-899407394)
when comparing them with Amaranth's.
