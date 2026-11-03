# Transceiver HDMI diagnostics

The [diagnostic target](examples/video_gt_diagnostics.py) generates color bars on a
Decklink Mini 4K or ModRetro M64. It uses block RAM and bypasses external memory and
framebuffer DMA. It exposes PLL lock, per-lane TX initialization and buffer status,
pixel/TX clock measurements, and a transmitter restart control.

This is a hardware bring-up aid, not a confirmed fix for
[LiteX-Boards #763](https://github.com/litex-hub/litex-boards/issues/763).
The GTP PHY now uses the M64 GTH PHY's shared TX word clock and direct raw TMDS
datapath. Digital tests check the lane words; they cannot verify serial lane deskew,
the physical reference clock, or the external HDMI retimer.

## Build and load

Run from this LiteX checkout, with current LiteX-Boards and LiteICLink installed.
`PYTHONPATH` ensures this checkout's PHY is used. The normal RISC-V toolchain,
Vivado and board programmer must be available in `PATH`.

```sh
PYTHONPATH="$PWD" python3 doc/examples/video_gt_diagnostics.py decklink \
    --output-dir=build/decklink-video-diag --build --load
```

Without `--load`, the helper only builds. With neither `--build` nor `--load`, it
generates RTL, constraints and CSR files. Decklink generates 1080p60; its PLL
reference still comes from the fabric, with the existing board DRC waiver. A
shared TX clock does not validate that reference path on hardware.

M64 generates 720p60 and requires an already configured 8T49N241 Q2 output. The
frequency argument describes that physical clock; it does not configure it. For
example, **only if Q2 is actually configured to 148.5 MHz**:

```sh
PYTHONPATH="$PWD" python3 doc/examples/video_gt_diagnostics.py m64 \
    --video-refclk-freq=148.5e6 --output-dir=build/m64-video-diag --build --load
```

## Read the diagnostics

Connect through the board's normal BIOS console. Wait at least two seconds after
configuration for the frequency meters. The generated `csr.csv` is authoritative;
addresses can change with board/LiteX revisions. In these default configurations:

| Register | Decklink | M64 |
| --- | --- | --- |
| `video_diag_restart` | `0xf0002800` | `0xf0005000` |
| `video_diag_status` | `0xf0002804` | `0xf0005004` |
| `video_diag_pixel_value` | `0xf0002808` | `0xf0005008` |
| `video_diag_tx_clk_value` | — | `0xf000500c` |
| `video_diag_tx_r_value` | `0xf000280c` | `0xf0005010` |
| `video_diag_tx_g_value` | `0xf0002810` | `0xf0005014` |
| `video_diag_tx_b_value` | `0xf0002814` | `0xf0005018` |

Status bit 0 is PLL lock. Following it are three bits per lane: TX-ready,
TXRESETDONE, TX-buffer error. The lane order is **r, g, b** for Decklink and
**clk, r, g, b** for M64. Bits are synchronized individually; read repeatedly
to distinguish a settled state from a transition.

| Expected settled result | Decklink | M64 |
| --- | --- | --- |
| Status: locked, ready, reset complete, no buffer errors | `0x1b7` | `0xdb7` |
| Pixel frequency | 148,500,000 Hz | 74,250,000 Hz |
| TX word frequency, all lanes | 74,250,000 Hz | 37,125,000 Hz |
| Serial line rate | 1.485 Gb/s | 742.5 Mb/s |

Frequency values are approximate, measured relative to the system clock. The
TX meters now observe a shared fabric clock; equal readings do not establish
alignment through the hard transceiver buffers or correct analog output.

For Decklink, capture the five words starting at status:

```text
mem_read 0xf0002804 20
```

For M64, capture the six words:

```text
mem_read 0xf0005004 24
```

The BIOS dumps bytes: for example, Decklink status `0x1b7` appears as
`b7 01 00 00` with the default little-endian VexRiscv CPU. Pasting the complete
dump is sufficient; no manual conversion is necessary.

To exercise TX startup again on Decklink:

```text
mem_write 0xf0002800 1
mem_write 0xf0002800 0
```

Use `0xf0005000` for M64. Wait two seconds, then repeat the readback. Also check
several cold power cycles. This control restarts the transmitters; it does not
reset or reprogram the entire board or its external clock generator.

## Report results

Please include:

- Whether the monitor detects a signal and displays stable color bars.
- CSR dumps after initial startup and after TX restart, plus cold-start consistency.
- The build log and repository revisions (`git rev-parse HEAD` in LiteX,
  LiteX-Boards and LiteICLink).
- For M64, the actual Q2 frequency and the existing `clkgen_status` / `hdmi_hpd`
  readbacks from its CSR map.

No PLL lock or incorrect clocks points toward reference-clock/initialization
issues. Lock with missing TX readiness or buffer errors points toward TX startup.
Healthy digital status with no video requires checking TMDS symbols, lane/polarity
mapping and the retimer/physical output. If color bars work, retest the original
framebuffer target to isolate VTG/DMA/memory behavior.
