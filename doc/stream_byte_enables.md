# Stream Byte Enables

Use a `be` payload field when a byte-oriented stream can carry partial words.
It has one bit per byte of `data`: bit `i` qualifies `data[8*i:8*(i+1)]`.
`be` is meaningful on **every accepted beat**, including intermediate beats.
A full 32-bit word has `be=0b1111`; a final three-byte word has `be=0b0111`.
`last` independently marks the end of the packet.

This has the same byte qualification as AXI Stream `keep`/`tkeep`. AXI interfaces
retain their standard `keep` name. Connect `keep` and `be` directly when their
widths and the endpoints' supported packet formats match. LiteX does not insert
byte enables into every endpoint: whole-word streams can keep their existing
layouts.

```python
layout = [("data", 32), ("be", 4)]
sink   = stream.Endpoint(layout)
```

## Handshaking And Supported Masks

`data`, `be`, `first`, `last` and packet parameters follow the usual stream
handshake. A producer must hold the presented beat while `valid & ~ready`.
Disabled bytes do not contribute to the payload; zero means no valid bytes,
never an implicit full word.

A mask does not imply byte compaction. FIFOs preserve masks. `StrideConverter`
splits/concatenates masks with data, clears unused slices after early termination
when widening, and terminates a narrowed packet at its last occupied slice.
Empty trailing slices are consumed internally. Sparse and intermediate zero
masks are preserved; an entirely empty final input beat produces one empty final
output beat when narrowing. Reverse conversion applies the same slice order to
data and byte enables. Packet parameters stay attached to the buffered word.

`Packetizer` and `Depacketizer` shift masks with data when headers are unaligned.
Header bytes are enabled; unused flush lanes are disabled. Their packet format
requires full intermediate beats and a nonzero, contiguous final mask starting
at byte zero. They do not compact sparse streams or support empty payloads.
They also retain their historical behavior for endpoints without a qualifier.

Applications should document any narrower contract. For example, LiteEth uses
full intermediate words and a contiguous nonzero final mask. An AXI producer
using sparse masks, empty beats or partial intermediate beats needs a compaction
stage before such a consumer.

## Migrating The Legacy Marker

The former `last_be` encoding marked only the last valid byte with a one-hot
value and used zero on intermediate beats. It is not a byte mask and must not be
renamed without changing the values. For a 32-bit stream:

| Beat | Legacy `last_be` | Native `be` |
| --- | --- | --- |
| Intermediate word | `0000` | `1111` |
| Final one-byte word | `0001` | `0001` |
| Final three-byte word | `0100` | `0111` |
| Final full word | `1000` (or legacy `0000`) | `1111` |

`stream.LastBEConverter(native_description)` provides an explicit legacy sink
and native source. `reverse=True` provides a native sink and legacy source.
It forwards data, parameters and handshakes without buffering. Put adapters at
integration boundaries, then use one representation throughout the datapath.
The adapter cannot represent sparse masks or empty native beats.

`stream.last_be_to_be()` and `stream.be_to_last_be()` provide the combinational
expressions when only a field mapping is needed. The generic packet helpers and
stride converter still accept legacy layouts so existing designs can migrate
independently. These helpers recognize stream qualifiers in the payload, not
unrelated packet parameters. In particular, PCIe TLP `first_be`/`last_be` fields
have protocol-defined meanings and must remain unchanged.
