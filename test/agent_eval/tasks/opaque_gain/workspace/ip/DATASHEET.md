# ACME Scaler IP - Datasheet (rev 1.0)

Fixed-point gain/offset stage for 16-bit unsigned samples, delivered as a synthesized netlist
(`acme_scaler.v`).

## Ports

| Port      | Dir | Width | Description                                    |
|-----------|-----|-------|------------------------------------------------|
| `sys_clk` | in  | 1     | Clock.                                         |
| `sys_rst` | in  | 1     | Synchronous reset, active high.                |
| `adr`     | in  | 3     | Register index (word address).                 |
| `we`      | in  | 1     | Write strobe (one cycle per write).            |
| `dat_w`   | in  | 32    | Write data.                                    |
| `dat_r`   | out | 32    | Read data of register `adr` (combinatorial).   |

## Registers

| Index | Offset | Name   | Access | Reset    | Description                                        |
|-------|--------|--------|--------|----------|----------------------------------------------------|
| 0     | 0x00   | ID     | RO     | 0xac5c0100 | IP identifier and revision.                      |
| 1     | 0x04   | CTRL   | RW     | 0        | bit 0: enable (output is 0 when disabled).         |
| 2     | 0x08   | GAIN   | RW     | 0x0100   | Gain, unsigned Q8.8 (0x0100 = 1.0).                |
| 3     | 0x0c   | OFFSET | RW     | 0        | Offset added after the gain, unsigned 16-bit.      |
| 4     | 0x10   | DIN    | RW     | 0        | Sample input; a write starts a computation.        |
| 5     | 0x14   | DOUT   | RO     | 0        | Result of the last computation.                    |
| 6     | 0x18   | -      | -      | -        | Reserved.                                          |
| 7     | 0x1c   | STATUS | RO     | 0        | bit 0: DOUT valid (cleared by a write to DIN).     |

## Function

    DOUT = min(((DIN * GAIN) >> 8) + OFFSET, 0xffff)

Latency: 2 cycles from the write to DIN to STATUS.valid.
