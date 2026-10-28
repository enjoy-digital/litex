LiteX's streams are group of signals (Migen's Record) used to create Sink/Source Endpoints on Modules and easily transfer data between them. LiteX's streams are a simplified compromise between AXI-4/Avalon-ST:
* `valid`: similar to AXI-4's `tvalid`.
* `ready`: similar to AXI-4's `tready`.
* `first` (used for packets only when needed): similar to Avalon-ST's `sop`, because it's sometimes useful to just easily know the start of a packet instead of deducing it from last as done in AXI-4.
* `last` (used for packets) : similar to AXI-4's `last`.
* `payload`: a Record with its own layout, similar to AXI-4's `tdata` that can evolve at each valid/ready transaction.
*  `param` (optional): a Record with its own layout, similar to AXI-4's `tuser` that can evolve at each start of packet.

LiteX's streams can be directly mapped to AXI-4 and adapted easily to AvalonST with: https://github.com/enjoy-digital/litex/blob/master/litex/soc/interconnect/avalon.py.

[alanvgreen](https://github.com/alanvgreen) has provided a [thorough description of LiteX streams and a helpful diagram](https://github.com/amaranth-lang/amaranth/issues/317#issuecomment-899407394).
