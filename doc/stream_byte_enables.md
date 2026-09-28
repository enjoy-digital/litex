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

The legacy stream encoding and its adapters are removed. Update producers,
consumers and layouts together; there is no zero-to-full fallback or implicit
conversion. Whole-word endpoints without a qualifier remain supported.

The helpers recognize stream qualifiers in the payload, not unrelated packet
parameters. PCIe TLP `first_be`/`last_be` fields have protocol-defined meanings
and remain unchanged.

## Byte-Mask Helpers

`stream.byte_enable_name(endpoint)` finds the payload's `be` or AXI `keep` field
and checks that it has one bit per data byte. It ignores packet parameters and
returns `None` for unqualified streams. Ambiguous or malformed qualifiers are
rejected. Width converters require matching qualifiers; packet helpers require
a qualifier on both endpoints or neither.

`stream.byte_count(be)` counts enabled bytes, including sparse masks.
`stream.byte_mask(count, width)` enables the lowest `count` bytes of a `width`-byte
word; a zero count produces zero and counts at least `width` produce a full mask.
These are combinatorial expressions. Converting a packet-length remainder to a
final-word mask is the caller's responsibility: a zero remainder of a nonempty
packet means a full final word, not zero valid bytes.
