#
# This file is part of LiteX.
#
# Copyright (c) 2021-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2021 Romain Dolbeau <romain@dolbeau.org>
# Copyright (c) 2022 Franck Jullien <franck.jullien@collshade.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import math

from migen import *
from migen.genlib.cdc import MultiReg

from litex.gen import *

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import stream
from litex.soc.cores.code_tmds import TMDSEncoder

from litex.build.io import SDROutput, DDROutput

# Video Constants ----------------------------------------------------------------------------------

hbits = 12
vbits = 12

# Video Timings ------------------------------------------------------------------------------------

video_timings = {
    "160x100@60Hz" : {
        "pix_clk"       : 1.655e6,
        "h_active"      : 160,
        "h_blanking"    : 80,
        "h_sync_offset" : 8,
        "h_sync_width"  : 32,
        "v_active"      : 100,
        "v_blanking"    : 15,
        "v_sync_offset" : 1,
        "v_sync_width"  : 8,
    },
    "320x200@60Hz" : {
        "pix_clk"       : 5.16e6,
        "h_active"      : 320,
        "h_blanking"    : 80,
        "h_sync_offset" : 8,
        "h_sync_width"  : 32,
        "v_active"      : 200,
        "v_blanking"    : 15,
        "v_sync_offset" : 1,
        "v_sync_width"  : 8,
    },
    "640x480@60Hz" : {
        "pix_clk"       : 25.175e6,
        "h_active"      : 640,
        "h_blanking"    : 160,
        "h_sync_offset" : 16,
        "h_sync_width"  : 96,
        "v_active"      : 480,
        "v_blanking"    : 45,
        "v_sync_offset" : 10,
        "v_sync_width"  : 2,
    },
    "640x480@75Hz" : {
        "pix_clk"       : 31.5e6,
        "h_active"      : 640,
        "h_blanking"    : 200,
        "h_sync_offset" : 16,
        "h_sync_width"  : 64,
        "v_active"      : 480,
        "v_blanking"    : 20,
        "v_sync_offset" : 1,
        "v_sync_width"  : 3,
    },
    "800x600@60Hz" : {
        "pix_clk"       : 40e6,
        "h_active"      : 800,
        "h_blanking"    : 256,
        "h_sync_offset" : 40,
        "h_sync_width"  : 128,
        "v_active"      : 600,
        "v_blanking"    : 28,
        "v_sync_offset" : 1,
        "v_sync_width"  : 4,
    },
    "800x600@75Hz": {
        "pix_clk"       : 49.5e6,
        "h_active"      : 800,
        "h_blanking"    : 256,
        "h_sync_offset" : 16,
        "h_sync_width"  : 80,
        "v_active"      : 600,
        "v_blanking"    : 25,
        "v_sync_offset" : 1,
        "v_sync_width"  : 3,
    },
    "1024x768@60Hz": {
        "pix_clk"       : 65e6,
        "h_active"      : 1024,
        "h_blanking"    : 320,
        "h_sync_offset" : 24,
        "h_sync_width"  : 136,
        "v_active"      : 768,
        "v_blanking"    : 38,
        "v_sync_offset" : 3,
        "v_sync_width"  : 6,
    },
    "1024x768@75Hz": {
        "pix_clk"       : 78.8e6,
        "h_active"      : 1024,
        "h_blanking"    : 288,
        "h_sync_offset" : 16,
        "h_sync_width"  : 96,
        "v_active"      : 768,
        "v_blanking"    : 32,
        "v_sync_offset" : 1,
        "v_sync_width"  : 3,
    },
    "1280x720@60Hz": {
        "pix_clk"       : 74.25e6,
        "h_active"      : 1280,
        "h_blanking"    : 370,
        "h_sync_offset" : 220,
        "h_sync_width"  : 40,
        "v_active"      : 720,
        "v_blanking"    : 30,
        "v_sync_offset" : 5,
        "v_sync_width"  : 5,
    },
    "1920x1080@30Hz": {
        "pix_clk"       : 89.01e6,
        "h_active"      : 1920,
        "h_blanking"    : 720,
        "h_sync_offset" : 528,
        "h_sync_width"  : 44,
        "v_active"      : 1080,
        "v_blanking"    : 45,
        "v_sync_offset" : 4,
        "v_sync_width"  : 5,
    },
    "1920x1080@60Hz": {
        "pix_clk"       : 148.5e6,
        "h_active"      : 1920,
        "h_blanking"    : 280,
        "h_sync_offset" : 88,
        "h_sync_width"  : 44,
        "v_active"      : 1080,
        "v_blanking"    : 45,
        "v_sync_offset" : 4,
        "v_sync_width"  : 5,
    },
    "1920x1200@60Hz": {
        "pix_clk"       : 148.2e6,
        "h_active"      : 1920,
        "h_blanking"    : 80,
        "h_sync_offset" : 8,
        "h_sync_width"  : 32,
        "v_active"      : 1200,
        "v_blanking"    : 35,
        "v_sync_offset" : 21,
        "v_sync_width"  : 8,
    },
}

# Video Timing Generator ---------------------------------------------------------------------------

video_timing_layout = [
    # Synchronization signals.
    ("hsync", 1),
    ("vsync", 1),
    ("de",    1),
    # Extended/Optional synchronization signals.
    ("hres",   hbits),
    ("vres",   vbits),
    ("hcount", hbits),
    ("vcount", vbits),
]

video_data_layout = [
    # Synchronization signals.
    ("hsync", 1),
    ("vsync", 1),
    ("de",    1),
    # Data signals.
    ("r",     8),
    ("g",     8),
    ("b",     8),
]

# DVI Color <-> channel mapping --------------------------------------------------------------------
_dvi_c2d = {"b": 0, "g": 1, "r": 2}

class VideoTimingGenerator(LiteXModule):
    def __init__(self, default_video_timings="800x600@60Hz"):
        # Check / Get Video Timings (can be str or dict)
        if isinstance(default_video_timings, str):
            try:
                self.video_timings = vt = video_timings[default_video_timings]
            except KeyError:
                msg = [f"Video Timings {default_video_timings} not supported, availables:"]
                for video_timing in video_timings.keys():
                    msg.append(f" - {video_timing} / {video_timings[video_timing]['pix_clk']/1e6:3.2f}MHz.")
                raise ValueError("\n".join(msg))
        else:
            self.video_timings = vt = default_video_timings

        # MMAP Control/Status Registers.
        self._enable      = CSRStorage(reset=1, description="Video Timing Generator enable.")

        self._hres        = CSRStorage(hbits, vt["h_active"],
            description="Horizontal active resolution.")
        self._hsync_start = CSRStorage(hbits, vt["h_active"] + vt["h_sync_offset"],
            description="Horizontal sync start.")
        self._hsync_end   = CSRStorage(hbits, vt["h_active"] + vt["h_sync_offset"] + vt["h_sync_width"],
            description="Horizontal sync end.")
        self._hscan       = CSRStorage(hbits, vt["h_active"] + vt["h_blanking"] - 1,
            description="Horizontal scan period.")

        self._vres        = CSRStorage(vbits, vt["v_active"],
            description="Vertical active resolution.")
        self._vsync_start = CSRStorage(vbits, vt["v_active"] + vt["v_sync_offset"],
            description="Vertical sync start.")
        self._vsync_end   = CSRStorage(vbits, vt["v_active"] + vt["v_sync_offset"] + vt["v_sync_width"],
            description="Vertical sync end.")
        self._vscan       = CSRStorage(vbits, vt["v_active"] + vt["v_blanking"] - 1,
            description="Vertical scan period.")

        # Video Timing Source
        self.source = source = stream.Endpoint(video_timing_layout)

        # # #

        # Resynchronize Enable to Video clock domain.
        self.enable = enable = Signal()
        self.specials += MultiReg(self._enable.storage, enable)

        # Resynchronize Horizontal Timings to Video clock domain.
        self.hres        = hres        = Signal(hbits)
        self.hsync_start = hsync_start = Signal(hbits)
        self.hsync_end   = hsync_end   = Signal(hbits)
        self.hscan       = hscan       = Signal(hbits)
        self.specials += MultiReg(self._hres.storage,        hres)
        self.specials += MultiReg(self._hsync_start.storage, hsync_start)
        self.specials += MultiReg(self._hsync_end.storage,   hsync_end)
        self.specials += MultiReg(self._hscan.storage,       hscan)

        # Resynchronize Vertical Timings to Video clock domain.
        self.vres        = vres        = Signal(vbits)
        self.vsync_start = vsync_start = Signal(vbits)
        self.vsync_end   = vsync_end   = Signal(vbits)
        self.vscan       = vscan       = Signal(vbits)
        self.specials += MultiReg(self._vres.storage,        vres)
        self.specials += MultiReg(self._vsync_start.storage, vsync_start)
        self.specials += MultiReg(self._vsync_end.storage,   vsync_end)
        self.specials += MultiReg(self._vscan.storage,       vscan)

        # Generate timings.
        hactive = Signal()
        vactive = Signal()
        fsm = FSM(reset_state="IDLE")
        fsm = ResetInserter()(fsm)
        self.fsm = fsm
        self.comb += fsm.reset.eq(~enable)
        fsm.act("IDLE",
            NextValue(hactive, 0),
            NextValue(vactive, 0),
            NextValue(source.hres, hres),
            NextValue(source.vres, vres),
            NextValue(source.hcount,  0),
            NextValue(source.vcount,  0),
            NextState("RUN")
        )
        self.comb += source.de.eq(hactive & vactive) # DE when both HActive and VActive.
        self.sync += source.first.eq((source.hcount ==     0) & (source.vcount ==     0)),
        self.sync += source.last.eq( (source.hcount == hscan) & (source.vcount == vscan)),
        fsm.act("RUN",
            source.valid.eq(1),
            If(source.ready,
                # Increment HCount.
                NextValue(source.hcount, source.hcount + 1),
                # Generate HActive / HSync.
                If(source.hcount == 0,           NextValue(hactive,       1)), # Start of HActive.
                If(source.hcount == hres,        NextValue(hactive,       0)), # End of HActive.
                If(source.hcount == hsync_start, NextValue(source.hsync,  1)),
                If(source.hcount == hsync_end,   NextValue(source.hsync,  0)), # End of HSync.
                If(source.hcount == hscan,       NextValue(source.hcount, 0)), # End of HScan.

                If(source.hcount == hsync_start,
                    # Increment VCount.
                    NextValue(source.vcount, source.vcount + 1),
                    # Generate VActive / VSync.
                    If(source.vcount == 0,           NextValue(vactive,       1)), # Start of VActive.
                    If(source.vcount == vres,        NextValue(vactive,       0)), # End of VActive.
                    If(source.vcount == vsync_start, NextValue(source.vsync,  1)),
                    If(source.vcount == vsync_end,   NextValue(source.vsync,  0)), # End of VSync.
                    If(source.vcount == vscan,       NextValue(source.vcount, 0))  # End of VScan.
                )
            )
        )

# Video Patterns -----------------------------------------------------------------------------------

class ColorBarsPattern(LiteXModule):
    """Color Bars Pattern"""
    def __init__(self):
        self.enable   = Signal(reset=1)
        self.vtg_sink = vtg_sink   = stream.Endpoint(video_timing_layout)
        self.source   = source = stream.Endpoint(video_data_layout)

        # # #

        enable = Signal()
        self.specials += MultiReg(self.enable, enable)

        # Control Path.
        pix = Signal(hbits)
        bar = Signal(3)

        fsm = FSM(reset_state="IDLE")
        fsm = ResetInserter()(fsm)
        self.fsm = fsm
        self.comb += fsm.reset.eq(~self.enable)
        fsm.act("IDLE",
            NextValue(pix, 0),
            NextValue(bar, 0),
            vtg_sink.ready.eq(1),
            If(vtg_sink.valid & vtg_sink.first & (vtg_sink.hcount == 0) & (vtg_sink.vcount == 0),
                vtg_sink.ready.eq(0),
                NextState("RUN")
            )
        )
        fsm.act("RUN",
            vtg_sink.connect(source, keep={"valid", "ready", "last", "de", "hsync", "vsync"}),
            If(source.valid & source.ready & source.de,
                NextValue(pix, pix + 1),
                If(pix == (vtg_sink.hres[3:] -1), # 8 Color Bars.
                    NextValue(pix, 0),
                    NextValue(bar, bar + 1)
                )
            ).Else(
                NextValue(pix, 0),
                NextValue(bar, 0)
            )
        )

        # Data Path.
        color_bar = [
            # R     G     B
            [0xff, 0xff, 0xff], # White
            [0xff, 0xff, 0x00], # Yellow
            [0x00, 0xff, 0xff], # Cyan
            [0x00, 0xff, 0x00], # Green
            [0xff, 0x00, 0xff], # Purple
            [0xff, 0x00, 0x00], # Red
            [0x00, 0x00, 0xff], # Blue
            [0x00, 0x00, 0x00], # Black
        ]
        cases = {}
        for i in range(8):
            cases[i] = [
                source.r.eq(color_bar[i][0]),
                source.g.eq(color_bar[i][1]),
                source.b.eq(color_bar[i][2])
            ]
        self.comb += Case(bar, cases)

# Video Terminal -----------------------------------------------------------------------------------

def import_bdf_font(filename):
    import csv
    font = [0]*16*256
    with open(filename) as f:
        reader = csv.reader(f, delimiter=" ")
        char          = None
        bitmap_enable = False
        bitmap_index  = 0
        for l in reader:
            if l[0] == "ENCODING":
                char = int(l[1], 0)
            if l[0] == "ENDCHAR":
                bitmap_enable = False
            if bitmap_enable:
                if char < 256:
                    font[char*16 + bitmap_index] = int("0x"+l[0], 0)
                bitmap_index += 1
            if l[0] == "BITMAP":
                bitmap_enable = True
                bitmap_index  = 0
    return font

class CSIInterpreter(LiteXModule):
    """Parses ANSI CSI (`ESC [ ... <final>`) sequences from an 8-bit stream.

    Two modes:
    - minimal (default): recognises only ESC[92m (green) and a quirky ESC[A
      that is wired as a full-screen clear.  Preserved for backward
      compatibility with the original implementation.
    - extended (opt-in via `extended=True`): proper multi-digit parameter
      parsing with ';' separators, and emission of command signals for CUP
      (ESC[row;colH), ED (ESC[2J), EL (ESC[K), cursor moves (ESC[nA/B/C/D)
      and SGR colour (ESC[91..97m).  The extended mode costs extra logic and
      a small parameter array; it is therefore off by default.
    """
    esc_start     = 0x1b
    csi_start     = ord("[")
    csi_param_min = 0x30
    csi_param_max = 0x3f

    def __init__(self, enable=True, extended=False):
        # The source endpoint tags every forwarded byte with the current
        # colour so the downstream FIFO preserves the tag — without this,
        # colour changes could silently reorder with the characters that
        # were already buffered downstream.
        self.sink   = sink   = stream.Endpoint([("data", 8)])
        self.source = source = stream.Endpoint([("data", 8), ("color", 4)])

        # Command outputs.  `color` and `clear_xy` are always present so the
        # rest of VideoTerminal does not need to care about the mode.
        self.color    = Signal(4)
        self.clear_xy = Signal()
        # Extended-mode outputs.  These stay asserted while the interpreter
        # sits in DECODE-CSI, and are cleared when the consumer (uart_fsm)
        # pulses `cmd_ack` — this avoids losing a 1-cycle pulse when the
        # consumer happens to be busy.
        self.clear_line = Signal()
        self.set_xy     = Signal()
        self.set_col    = Signal(8)
        self.set_row    = Signal(8)
        self.move_up    = Signal()
        self.move_down  = Signal()
        self.move_left  = Signal()
        self.move_right = Signal()
        self.move_count = Signal(8)
        self.cmd_ack    = Signal()

        # # #

        # `source.color` is always driven by the latched colour register, so
        # every byte the interpreter forwards (CSI disabled, minimal or
        # extended mode) carries the colour it was emitted under.
        self.comb += source.color.eq(self.color)

        if not enable:
            self.comb += self.sink.connect(self.source, omit={"color"})
            return

        if not extended:
            self._build_minimal_fsm(sink, source)
        else:
            self._build_extended_fsm(sink, source)

    # ----------------------------------------------------------------- minimal
    def _build_minimal_fsm(self, sink, source):
        # Preserved verbatim (modulo comments) from the original
        # implementation — known-quirky, but matches what existing hardware
        # already runs.
        csi_count = Signal(3)
        csi_bytes = Array([Signal(8) for _ in range(8)])
        csi_final = Signal(8)

        self.fsm = fsm = FSM(reset_state="RECOPY")
        fsm.act("RECOPY",
            sink.connect(source, omit={"color"}),
            If(sink.valid & (sink.data == self.esc_start),
                source.valid.eq(0),
                sink.ready.eq(1),
                NextState("GET-CSI-START")
            )
        )
        fsm.act("GET-CSI-START",
            sink.ready.eq(1),
            If(sink.valid,
                If(sink.data == self.csi_start,
                    NextValue(csi_count, 0),
                    NextState("GET-CSI-PARAMETERS")
                ).Else(
                    NextState("RECOPY")
                )
            )
        )
        fsm.act("GET-CSI-PARAMETERS",
            If(sink.valid,
                If((sink.data >= self.csi_param_min) & (sink.data <= self.csi_param_max),
                    sink.ready.eq(1),
                    NextValue(csi_count, csi_count + 1),
                    NextValue(csi_bytes[csi_count], sink.data),
                ).Else(
                    NextState("GET-CSI-FINAL")
                )
            )
        )
        fsm.act("GET-CSI-FINAL",
            sink.ready.eq(1),
            NextValue(csi_final, sink.data),
            NextState("DECODE-CSI")
        )
        fsm.act("DECODE-CSI",
            If(csi_final == ord("m"),
                # NB: the inner test uses Python `and`, which collapses the
                # two-byte comparison to just `bytes[1] == '2'`.  Kept for
                # bit-compatibility with existing hardware.
                If((csi_bytes[0] == ord("9")) and (csi_bytes[1] == ord("2")),
                    NextValue(self.color, 1),
                ).Else(
                    NextValue(self.color, 0),
                ),
            ),
            If(csi_final == ord("A"), # Historically wired as full-clear.
                self.clear_xy.eq(1)
            ),
            NextState("RECOPY")
        )

    # ---------------------------------------------------------------- extended
    def _build_extended_fsm(self, sink, source):
        # Up to four numeric parameters are parsed into `params`.
        # `params_count` tracks how many have been seen (0..3); `cur_param`
        # is the accumulator for the digit currently under parse.
        n_params     = 4
        params       = Array([Signal(8) for _ in range(n_params)])
        params_count = Signal(max=n_params + 1)
        cur_param    = Signal(8)
        cur_dirty    = Signal()  # True if any digit has been pushed into cur_param
        csi_final    = Signal(8)

        def param_or_default(idx, default):
            # Returns the parsed param if present, else `default`.
            # `params_count > idx` tells us param `idx` was set.
            return Mux(params_count > idx, params[idx], default)

        self.fsm = fsm = FSM(reset_state="RECOPY")
        fsm.act("RECOPY",
            sink.connect(source, omit={"color"}),
            If(sink.valid & (sink.data == self.esc_start),
                source.valid.eq(0),
                sink.ready.eq(1),
                NextState("GET-CSI-START")
            )
        )
        fsm.act("GET-CSI-START",
            sink.ready.eq(1),
            If(sink.valid,
                If(sink.data == self.csi_start,
                    NextValue(params_count, 0),
                    NextValue(cur_param, 0),
                    NextValue(cur_dirty, 0),
                    # Zero the param array so previous sequences don't leak in.
                    *[NextValue(params[i], 0) for i in range(n_params)],
                    NextState("GET-CSI-PARAMETERS")
                ).Else(
                    NextState("RECOPY")
                )
            )
        )
        fsm.act("GET-CSI-PARAMETERS",
            If(sink.valid,
                # ASCII digit: accumulate into cur_param (decimal).
                If((sink.data >= ord("0")) & (sink.data <= ord("9")),
                    sink.ready.eq(1),
                    NextValue(cur_param, cur_param * 10 + (sink.data - ord("0"))),
                    NextValue(cur_dirty, 1),
                # Separator: push current accumulator if any digits were seen
                # (an empty slot keeps the default via param_or_default).
                ).Elif(sink.data == ord(";"),
                    sink.ready.eq(1),
                    If(cur_dirty & (params_count < n_params),
                        NextValue(params[params_count], cur_param),
                        NextValue(params_count, params_count + 1),
                    ),
                    NextValue(cur_param, 0),
                    NextValue(cur_dirty, 0),
                # Any other byte → final (not consumed here).
                ).Else(
                    # Commit the pending param before moving on.
                    If(cur_dirty & (params_count < n_params),
                        NextValue(params[params_count], cur_param),
                        NextValue(params_count, params_count + 1),
                    ),
                    NextState("GET-CSI-FINAL")
                )
            )
        )
        fsm.act("GET-CSI-FINAL",
            If(sink.valid,
                sink.ready.eq(1),
                NextValue(csi_final, sink.data),
                NextState("DECODE-CSI")
            )
        )
        # In DECODE-CSI we drive the command signals combinationally and
        # stall here until uart_fsm acknowledges them (cmd_ack).  SGR (color)
        # and unknown finals need no downstream action, so we flow through
        # without waiting.
        needs_ack = Signal()
        self.comb += [
            self.move_count.eq(param_or_default(0, 1)),
            self.set_row.eq(param_or_default(0, 1) - 1),
            self.set_col.eq(param_or_default(1, 1) - 1),
        ]
        fsm.act("DECODE-CSI",
            # SGR: ESC[<n>m — colour set.  N=0 or missing → default (0).
            # N in 91..97 mapped to palette indices 1..7.  Everything else
            # resets to 0 so malformed sequences don't linger.
            If(csi_final == ord("m"),
                If((params[0] >= 91) & (params[0] <= 97),
                    NextValue(self.color, params[0] - 90),
                ).Else(
                    NextValue(self.color, 0),
                ),
            # CUP: ESC[<row>;<col>H (and ESC[H variant `f`) — absolute
            # cursor position (1-indexed in ANSI, 0-indexed internally).
            ).Elif((csi_final == ord("H")) | (csi_final == ord("f")),
                self.set_xy.eq(1),
                needs_ack.eq(1),
            # ED: ESC[<n>J — erase display.  Only n=2 (whole screen) is
            # honoured here; partial clears would need extra uart_fsm
            # states and aren't worth the cost for typical use.
            ).Elif(csi_final == ord("J"),
                If(params[0] == 2,
                    self.clear_xy.eq(1),
                    needs_ack.eq(1),
                ),
            # EL: ESC[K — erase from cursor to end of line.
            ).Elif(csi_final == ord("K"),
                self.clear_line.eq(1),
                needs_ack.eq(1),
            # Cursor moves.  Default count is 1 (handled in param_or_default).
            ).Elif(csi_final == ord("A"),
                self.move_up.eq(1),
                needs_ack.eq(1),
            ).Elif(csi_final == ord("B"),
                self.move_down.eq(1),
                needs_ack.eq(1),
            ).Elif(csi_final == ord("C"),
                self.move_right.eq(1),
                needs_ack.eq(1),
            ).Elif(csi_final == ord("D"),
                self.move_left.eq(1),
                needs_ack.eq(1),
            ),
            If(~needs_ack | self.cmd_ack,
                NextState("RECOPY")
            )
        )

class VideoTerminal(LiteXModule):
    # Historical palette (white + accent green) used by every existing board
    # support package; kept as the default so a plain `VideoTerminal(...)`
    # still produces the same pixels as before.
    default_palette = [0xffffff, 0x89e234]

    # When the caller opts into `with_extended_csi=True` but does not supply
    # a palette, this 8-entry ANSI-ish table is used.  Index 0 stays at the
    # historical white so non-coloured text still looks unchanged.
    default_extended_palette = [
        0xffffff,  # 0 default (white)
        0xe01b24,  # 1 red       — ESC[91m
        0x89e234,  # 2 green     — ESC[92m
        0xf6d32d,  # 3 yellow    — ESC[93m
        0x1c71d8,  # 4 blue      — ESC[94m
        0x9141ac,  # 5 magenta   — ESC[95m
        0x2aa198,  # 6 cyan      — ESC[96m
        0xffffff,  # 7 bright    — ESC[97m
    ]

    def __init__(self, hres=800, vres=600, with_csi_interpreter=True, with_extended_csi=False,
                 visible_cols=None, font=None, palette=None, destructive_cr=True):
        self.enable    = Signal(reset=1)
        self.vtg_sink  = vtg_sink   = stream.Endpoint(video_timing_layout)
        self.uart_sink = uart_sink  = stream.Endpoint([("data", 8)])
        self.source    = source     = stream.Endpoint(video_data_layout)

        # # #

        csi_width = 8 if with_csi_interpreter else 0

        # `visible_cols` is the number of character columns that are actually
        # displayed (and at which the cursor wraps to the next line).  The
        # underlying buffer is always sized to `term_colums` (128, next power
        # of two) so a single Y multiplication addresses it.  Defaulting to 80
        # preserves the historical behavior of this module.
        if visible_cols is None:
            visible_cols = 80

        # Palette: index → 24-bit RGB.  Defaults differ based on whether the
        # extended CSI interpreter is in use (which can address up to 8
        # palette entries); both defaults keep index 0 at the historical
        # white so existing hardware renders the same as before.
        if palette is None:
            palette = self.default_extended_palette if with_extended_csi else self.default_palette

        # Font Mem.
        # ---------
        # FIXME: Store Font in LiteX?
        if font is None:
            if not os.path.exists("ter-u16b.bdf"):
                os.system("wget https://github.com/enjoy-digital/litex/files/6076336/ter-u16b.txt")
                os.system("mv ter-u16b.txt ter-u16b.bdf")
            font = import_bdf_font("ter-u16b.bdf")
        font_width  = 8
        font_heigth = 16
        font_mem    = Memory(width=8, depth=4096, init=font)
        font_rdport = font_mem.get_port(has_re=True)
        self.specials += font_mem, font_rdport

        # Terminal Mem.
        # -------------
        term_colums = 128 # 80 rounded to next power of two.
        term_lines  = math.floor(vres/font_heigth)
        term_depth  = term_colums * term_lines
        term_init   = [ord(c) for c in [" "]*term_colums*term_lines]
        term_mem    = Memory(width=font_width + csi_width, depth=term_depth, init=term_init)
        term_wrport = term_mem.get_port(write_capable=True)
        term_rdport = term_mem.get_port(has_re=True)
        self.specials += term_mem, term_wrport, term_rdport

        # Expose parameters/memories for testbenches and external introspection.
        # The memories are excluded from AutoCSR's `get_memories` scan —
        # otherwise LiteX would synthesise a CSR-banked third port on them
        # and dual-port BRAMs (e.g. ECP5 DP16KD) can't satisfy that.
        self.term_mem    = term_mem
        self.font_mem    = font_mem
        self.autocsr_exclude = {"term_mem", "font_mem"}
        self.term_colums  = term_colums
        self.term_lines   = term_lines
        self.visible_cols = visible_cols
        self.font_width   = font_width
        self.font_heigth  = font_heigth

        # UART Terminal Fill.
        # -------------------

        # Optional CSI Interpreter.
        self.csi_interpreter = CSIInterpreter(enable=with_csi_interpreter, extended=with_extended_csi)
        self.comb += uart_sink.connect(self.csi_interpreter.sink)
        uart_sink = self.csi_interpreter.source

        # The FIFO carries colour alongside the character so the attribute
        # used at WRITE-time matches the colour that was latched when this
        # particular byte left the CSI interpreter.  Without this, any bytes
        # queued in the FIFO would be re-coloured by later ESC[ sequences.
        fifo_layout = [("data", 8), ("color", 4)] if csi_width else [("data", 8)]
        self.uart_fifo = stream.SyncFIFO(fifo_layout, 8)
        if csi_width:
            self.comb += uart_sink.connect(self.uart_fifo.sink)
        else:
            self.comb += uart_sink.connect(self.uart_fifo.sink, omit={"color"})
        uart_sink = self.uart_fifo.source

        # UART Reception and Terminal Fill.
        x_term = term_wrport.adr[:7]
        y_term = term_wrport.adr[7:]
        self.y_term_rollover = y_term_rollover = Signal()
        self.uart_fsm = uart_fsm = FSM(reset_state="RESET")
        uart_fsm.act("RESET",
            NextValue(x_term, 0),
            NextValue(y_term, 0),
            NextState("CLEAR-XY")
        )
        uart_fsm.act("CLEAR-XY",
            term_wrport.we.eq(1),
            term_wrport.dat_w[:font_width].eq(ord(" ")),
            NextValue(y_term_rollover, 0),
            NextValue(x_term, x_term + 1),
            If(x_term == (term_colums - 1),
                NextValue(x_term, 0),
                NextValue(y_term, y_term + 1),
                If(y_term == (term_lines - 1),
                    NextValue(y_term, 0),
                    NextState("IDLE")
                )
            )
        )
        # Next-tab-stop for HT: round x_term up to the next multiple of 8,
        # then clamp to the last visible column so TAB near the right margin
        # does not push the cursor off-screen.
        tab_next = Signal(8)
        self.comb += tab_next.eq(Cat(Signal(3, reset=0), x_term[3:] + 1))
        # Aggregate extended-CSI command flags so the IDLE state can serve
        # them as one branch.  All of these are asserted by the interpreter
        # while it stalls in DECODE-CSI waiting for cmd_ack.
        csi_cmd_pending = Signal()
        if with_extended_csi:
            csi = self.csi_interpreter
            self.comb += csi_cmd_pending.eq(
                csi.set_xy | csi.clear_line | csi.move_up |
                csi.move_down | csi.move_left | csi.move_right
            )
        uart_fsm.act("IDLE",
            If(uart_sink.valid,
                # Line-feed (LF): advance to next row.
                If(uart_sink.data == 0x0a,
                    uart_sink.ready.eq(1),
                    NextState("INCR-Y")
                # Carriage return (CR).  In destructive mode (the historical
                # behavior) this also erases the current line — go through
                # RST-X which kicks CLEAR-X.  In non-destructive mode, just
                # move the cursor back to column 0, matching ANSI terminals.
                ).Elif(uart_sink.data == 0x0d,
                    uart_sink.ready.eq(1),
                    *([NextState("RST-X")] if destructive_cr else [NextValue(x_term, 0)])
                # Horizontal tab (HT): move cursor to the next 8-column stop.
                ).Elif(uart_sink.data == 0x09,
                    uart_sink.ready.eq(1),
                    NextState("TAB-X")
                # Backspace (BS): move cursor one column left (no erase).
                ).Elif(uart_sink.data == 0x08,
                    uart_sink.ready.eq(1),
                    NextState("DECR-X")
                # Bell (BEL): silently consume.
                ).Elif(uart_sink.data == 0x07,
                    uart_sink.ready.eq(1)
                # Form-feed (FF): clear the whole screen.
                ).Elif(uart_sink.data == 0x0c,
                    uart_sink.ready.eq(1),
                    NextState("RST-XY")
                ).Else(
                    NextState("WRITE")
                )
            ),
            # CSI-requested full-screen clear (available in both modes —
            # minimal uses it for ESC[A, extended for ESC[2J).  Only ack
            # once the FIFO has drained so that any bytes queued before the
            # clear have already been applied.
            If(self.csi_interpreter.clear_xy & ~uart_sink.valid,
                self.csi_interpreter.cmd_ack.eq(1),
                NextState("RST-XY")
            ),
            # Extended cursor/line commands.  Like the full-clear above,
            # only acted upon once the FIFO is empty.  The CSI interpreter
            # stalls in DECODE-CSI while any command signal is held, so it's
            # safe to poll these and ack with a single pulse.
            *([
                If(csi_cmd_pending & ~uart_sink.valid,
                    self.csi_interpreter.cmd_ack.eq(1),
                    If(self.csi_interpreter.set_xy,
                        NextValue(x_term, self.csi_interpreter.set_col),
                        NextValue(y_term, self.csi_interpreter.set_row),
                    ),
                    If(self.csi_interpreter.clear_line,
                        NextState("CLEAR-X")
                    ),
                    If(self.csi_interpreter.move_up,
                        If(self.csi_interpreter.move_count >= y_term,
                            NextValue(y_term, 0)
                        ).Else(
                            NextValue(y_term, y_term - self.csi_interpreter.move_count)
                        ),
                    ),
                    If(self.csi_interpreter.move_down,
                        If(y_term + self.csi_interpreter.move_count >= term_lines,
                            NextValue(y_term, term_lines - 1)
                        ).Else(
                            NextValue(y_term, y_term + self.csi_interpreter.move_count)
                        ),
                    ),
                    If(self.csi_interpreter.move_left,
                        If(self.csi_interpreter.move_count >= x_term,
                            NextValue(x_term, 0)
                        ).Else(
                            NextValue(x_term, x_term - self.csi_interpreter.move_count)
                        ),
                    ),
                    If(self.csi_interpreter.move_right,
                        If(x_term + self.csi_interpreter.move_count >= visible_cols,
                            NextValue(x_term, visible_cols - 1)
                        ).Else(
                            NextValue(x_term, x_term + self.csi_interpreter.move_count)
                        ),
                    ),
                )
            ] if with_extended_csi else []),
        )
        uart_fsm.act("WRITE",
            uart_sink.ready.eq(1),
            term_wrport.we.eq(1),
            term_wrport.dat_w[:font_width].eq(uart_sink.data),
            # The character's colour travels alongside its data in the FIFO
            # (see `fifo_layout` above), so it lines up with the glyph even
            # if the CSI interpreter has since moved on to another colour.
            *([term_wrport.dat_w[font_width:].eq(uart_sink.color)] if csi_width else []),
            NextState("INCR-X")
        )
        uart_fsm.act("RST-X",
            NextValue(x_term, 0),
            NextState("CLEAR-X")
        )
        uart_fsm.act("RST-XY",
            # Rewind (x, y) to (0, 0) before running CLEAR-XY so the clear
            # visits every cell regardless of where the cursor was.
            NextValue(x_term, 0),
            NextValue(y_term, 0),
            NextState("CLEAR-XY")
        )
        uart_fsm.act("DECR-X",
            If(x_term != 0,
                NextValue(x_term, x_term - 1)
            ),
            NextState("IDLE")
        )
        uart_fsm.act("TAB-X",
            If(tab_next >= visible_cols,
                NextValue(x_term, visible_cols - 1)
            ).Else(
                NextValue(x_term, tab_next)
            ),
            NextState("IDLE")
        )
        uart_fsm.act("INCR-X",
            NextValue(x_term, x_term + 1),
            NextState("IDLE"),
            If(x_term == (visible_cols - 1),
                NextValue(x_term, 0),
                NextState("INCR-Y")
            )
        )
        uart_fsm.act("RST-Y",
            NextValue(y_term, 0),
            NextState("CLEAR-X")
        )
        uart_fsm.act("INCR-Y",
            NextValue(y_term, y_term + 1),
            NextState("CLEAR-X"),
            If(y_term == (term_lines - 1),
                NextValue(y_term_rollover, 1),
                NextState("RST-Y")
            )
        )
        uart_fsm.act("CLEAR-X",
            NextValue(x_term, x_term + 1),
            term_wrport.we.eq(1),
            term_wrport.dat_w[:font_width].eq(ord(" ")),
            If(x_term == (term_colums - 1),
                NextValue(x_term, 0),
                NextState("IDLE")
            )
        )

        # Video Generation.
        # -----------------
        ce = (vtg_sink.valid & vtg_sink.ready)

        # Timing delay line.
        latency     = 2
        timing_bufs = [stream.Buffer(video_timing_layout) for i in range(latency)]
        self.comb += vtg_sink.connect(timing_bufs[0].sink)
        for i in range(len(timing_bufs) - 1):
            self.comb += timing_bufs[i].source.connect(timing_bufs[i+1].sink)
        self.comb += timing_bufs[-1].source.connect(source, keep={"valid", "ready", "last", "de", "hsync", "vsync"})
        self.submodules += timing_bufs

        # Compute X/Y position.
        x = vtg_sink.hcount[int(math.log2(font_width)):]
        y = vtg_sink.vcount[int(math.log2(font_heigth)):]
        y_rollover = Signal(8)
        self.comb += [
            If(~y_term_rollover,
                y_rollover.eq(y)
            ).Else(
                # FIXME: Use Modulo.
                If((y + y_term + 1) >= term_lines,
                    y_rollover.eq(y + y_term + 1 - term_lines)
                ).Else(
                    y_rollover.eq(y + y_term + 1)
                ),
            )
        ]

        # Get character from Terminal Mem.
        term_dat_r = Signal(font_width)
        self.comb += term_rdport.re.eq(ce)
        self.comb += term_rdport.adr.eq(x + y_rollover*term_colums)
        self.comb += [
            term_dat_r.eq(term_rdport.dat_r[:font_width]),
            If((x >= visible_cols) | (y >= term_lines),
                term_dat_r.eq(ord(" ")), # Out of range, generate space.
            )
        ]

        # Translate character to video data through Font Mem.
        self.comb += font_rdport.re.eq(ce)
        self.comb += font_rdport.adr.eq(term_dat_r*font_heigth + timing_bufs[0].source.vcount[:4])
        bit = Signal()
        cases = {}
        for i in range(font_width):
            cases[i] = [bit.eq(font_rdport.dat_r[font_width-1-i])]
        self.comb += Case(timing_bufs[1].source.hcount[:int(math.log2(font_width))], cases)
        # Palette lookup: the `csi_width` high bits of the memory word index
        # into the user-supplied palette.  Out-of-range indices fall back to
        # palette[0] (the default foreground) rather than producing random
        # colours.
        palette_cases = {
            i: [Cat(source.r, source.g, source.b).eq(rgb)]
            for i, rgb in enumerate(palette)
        }
        palette_cases["default"] = [Cat(source.r, source.g, source.b).eq(palette[0])]
        self.comb += [
            If(bit,
                Case(term_rdport.dat_r[font_width:], palette_cases)
            ).Else(
                Cat(source.r, source.g, source.b).eq(0x000000),
            )
        ]

# Video FrameBuffer --------------------------------------------------------------------------------

class VideoFrameBuffer(LiteXModule):
    """Video FrameBuffer"""
    def __init__(self, dram_port, hres=800, vres=600, base=0x00000000, fifo_depth=64*KILOBYTE, clock_domain="sys", clock_faster_than_sys=False, format="rgb888"):
        self.vtg_sink  = vtg_sink = stream.Endpoint(video_timing_layout)
        self.source    = source   = stream.Endpoint(video_data_layout)
        self.underflow = Signal()

        self.depth = depth = {
            "rgb888" : 32,
            "rgb565" : 16,
            "rgb332" : 8,
            "mono8"  : 8,
            "mono1"  : 1,
        }[format]

        # # #

        # Video DMA.
        from litedram.frontend.dma import LiteDRAMDMAReader
        self.dma = LiteDRAMDMAReader(dram_port, fifo_depth=fifo_depth//(dram_port.data_width//8), fifo_buffered=True)
        self.dma.add_csr(
            default_base   = base,
            default_length = hres*vres*depth//8, # 32-bit RGB-888 or 16-bit RGB-565
            default_enable = 0,
            default_loop   = 1
        )

        # If DRAM Data Width > depth and Video clock is faster than sys_clk:
        if (dram_port.data_width > depth) and clock_faster_than_sys:
            # Do Clock Domain Crossing first...
            self.cdc = stream.ClockDomainCrossing([("data", dram_port.data_width)], cd_from="sys", cd_to=clock_domain)
            self.comb += self.dma.source.connect(self.cdc.sink)
            # ... and then Data-Width Conversion.
            self.conv = ClockDomainsRenamer(clock_domain)(stream.Converter(dram_port.data_width, depth))
            self.comb += self.cdc.source.connect(self.conv.sink)
            video_pipe_source = self.conv.source
        # Elsif DRAM Data Width <= depth or Video clock is slower than sys_clk:
        else:
            # Do Data-Width Conversion first...
            self.conv = stream.Converter(dram_port.data_width, depth)
            self.comb += self.dma.source.connect(self.conv.sink)
            # ... and then Clock Domain Crossing.
            self.cdc = stream.ClockDomainCrossing([("data", depth)], cd_from="sys", cd_to=clock_domain)
            self.comb += self.conv.source.connect(self.cdc.sink)
            if (dram_port.data_width < depth) and (depth == 32): # FIXME.
                self.comb += [
                    self.cdc.sink.data[ 0: 8].eq(self.conv.source.data[16:24]),
                    self.cdc.sink.data[16:24].eq(self.conv.source.data[ 0: 8]),
                ]
            video_pipe_source = self.cdc.source

        # Video Synchronization/Generation.
        first = Signal()
        fsm = FSM(reset_state="SYNC")
        fsm = ClockDomainsRenamer(clock_domain)(fsm)
        fsm = ResetInserter()(fsm)
        self.submodules += fsm
        self.specials += MultiReg(self.dma.fsm.reset, fsm.reset, clock_domain)
        fsm.act("SYNC",
            vtg_sink.ready.eq(1),
            If(fsm.reset,
                vtg_sink.ready.eq(0),
                NextValue(first, 1)
            ),
            If(vtg_sink.valid & vtg_sink.last,
                NextState("RUN")
            ),
            vtg_sink.connect(source, keep={"hsync", "vsync"}),
        )
        fsm.act("RUN",
            vtg_sink.ready.eq(1),
            If(vtg_sink.valid & vtg_sink.de,
                video_pipe_source.connect(source, keep={"valid", "ready"}),
                If(first,
                    source.valid.eq(0)
                ),
                vtg_sink.ready.eq(source.valid & source.ready),
                If(video_pipe_source.valid & video_pipe_source.last,
                    NextValue(first, 0),
                    NextState("SYNC"),
                )
            ),
            vtg_sink.connect(source, keep={"de", "hsync", "vsync"}),
        )

        if (depth == 32):
            self.comb += [
                source.r.eq(video_pipe_source.data[ 0: 8]),
                source.g.eq(video_pipe_source.data[ 8:16]),
                source.b.eq(video_pipe_source.data[16:24]),
            ]
        elif (depth == 16):
            self.comb += [
                source.r.eq(Cat(Signal(3, reset=0), video_pipe_source.data[11:16])),
                source.g.eq(Cat(Signal(2, reset=0), video_pipe_source.data[ 5:11])),
                source.b.eq(Cat(Signal(3, reset=0), video_pipe_source.data[ 0: 5])),
            ]
        elif (depth == 8 and format == "rgb332"):
            self.comb += [
                source.r.eq(Cat(Signal(5, reset=0), video_pipe_source.data[5:8])),
                source.g.eq(Cat(Signal(5, reset=0), video_pipe_source.data[2:5])),
                source.b.eq(Cat(Signal(6, reset=0), video_pipe_source.data[0:2])),
            ]
        elif (depth == 8 and format == "mono8"):
            self.comb += [
                source.r.eq(video_pipe_source.data[0:8]),
                source.g.eq(video_pipe_source.data[0:8]),
                source.b.eq(video_pipe_source.data[0:8]),
            ]
        else: # depth == 1
            self.comb += [
               source.r.eq(Cat(Signal(7, reset=0), video_pipe_source.data[0:1])),
               source.g.eq(Cat(Signal(7, reset=0), video_pipe_source.data[0:1])),
               source.b.eq(Cat(Signal(7, reset=0), video_pipe_source.data[0:1])),
            ]

        # Underflow.
        self.comb += self.underflow.eq(~source.valid)

# Video PHYs ---------------------------------------------------------------------------------------

# Generic (Very Generic PHY supporting VGA/DVI and variations).

class VideoGenericPHY(LiteXModule):
    def __init__(self, pads, clock_domain="sys", with_clk_ddr_output=True):
        self.sink = sink = stream.Endpoint(video_data_layout)

        # # #

        # Always ack Sink, no backpressure.
        self.comb += sink.ready.eq(1)

        # Drive Clk.
        if hasattr(pads, "clk"):
            if with_clk_ddr_output:
                self.specials += DDROutput(i1=1, i2=0, o=pads.clk, clk=ClockSignal(clock_domain))
            else:
                self.comb += pads.clk.eq(ClockSignal(clock_domain))

        # Drive Controls.
        if hasattr(pads, "de"):
            self.specials += SDROutput(i=sink.de, o=pads.de, clk=ClockSignal(clock_domain))
        if hasattr(pads, "hsync_n") and hasattr(pads, "vsync_n"):
            self.specials += SDROutput(i=~sink.hsync, o=pads.hsync_n, clk=ClockSignal(clock_domain))
            self.specials += SDROutput(i=~sink.vsync, o=pads.vsync_n, clk=ClockSignal(clock_domain))
        else:
            self.specials += SDROutput(i=sink.hsync,  o=pads.hsync,   clk=ClockSignal(clock_domain))
            self.specials += SDROutput(i=sink.vsync,  o=pads.vsync,   clk=ClockSignal(clock_domain))

        # Drive Datas.
        cbits  = len(pads.r)
        cshift = (8 - cbits)
        for i in range(cbits):
            # VGA monitors interpret minimum value as black so ensure data is set to 0 during blanking.
            self.specials += SDROutput(i=sink.r[cshift + i] & sink.de, o=pads.r[i], clk=ClockSignal(clock_domain))
            self.specials += SDROutput(i=sink.g[cshift + i] & sink.de, o=pads.g[i], clk=ClockSignal(clock_domain))
            self.specials += SDROutput(i=sink.b[cshift + i] & sink.de, o=pads.b[i], clk=ClockSignal(clock_domain))

# VGA (Generic).

class VideoVGAPHY(VideoGenericPHY): pass

# DVI (Generic).

class VideoDVIPHY(VideoGenericPHY): pass

# HDMI (Generic).

class VideoHDMI10to1Serializer(LiteXModule):
    def __init__(self, data_i, data_o, clock_domain):
        # Clock Domain Crossing.
        self.cdc = stream.ClockDomainCrossing([("data", 10)], cd_from=clock_domain, cd_to=clock_domain + "5x")
        self.comb += self.cdc.sink.valid.eq(1)
        self.comb += self.cdc.sink.data.eq(data_i)

        # 10:2 Gearbox.
        self.gearbox = ClockDomainsRenamer(clock_domain + "5x")(stream.Gearbox(i_dw=10, o_dw=2, msb_first=False))
        self.comb += self.cdc.source.connect(self.gearbox.sink)

        # 2:1 Output DDR.
        self.comb += self.gearbox.source.ready.eq(1)
        self.specials += DDROutput(
            clk = ClockSignal(clock_domain + "5x"),
            i1  = self.gearbox.source.data[0],
            i2  = self.gearbox.source.data[1],
            o   = data_o,
        )

class VideoHDMIPHY(LiteXModule):
    def __init__(self, pads, clock_domain="sys", pn_swap=[]):
        self.sink = sink = stream.Endpoint(video_data_layout)

        # # #

        # Determine driven polarities:
        # - p only for True/Pseudo Differential.
        # - p and n for Fake Differential.
        drive_pols = []
        for pol in ["p", "n"]:
            if hasattr(pads, f"clk_{pol}"):
                drive_pols.append(pol)

        # Always ack Sink, no backpressure.
        self.comb += sink.ready.eq(1)

        # Clocking + Pseudo Differential Signaling.
        for pol in drive_pols:
            self.specials += DDROutput(
                i1  = {"p" : 1, "n" : 0}[pol],
                i2  = {"p" : 0, "n" : 1}[pol],
                o   = getattr(pads, f"clk_{pol}"),
                clk = ClockSignal(clock_domain),
            )

        # Encode/Serialize Datas.
        for pol in drive_pols:
            for color, channel in _dvi_c2d.items():
                # TMDS Encoding.
                encoder = ClockDomainsRenamer(clock_domain)(TMDSEncoder())
                self.add_module(name=f"{color}_encoder_{pol}", module=encoder)
                self.comb += encoder.d.eq(getattr(sink, color))
                self.comb += encoder.c.eq(Cat(sink.hsync, sink.vsync) if channel == 0 else 0)
                self.comb += encoder.de.eq(sink.de)

                # 10:1 Serialization + Pseudo Differential Signaling.
                data_i = encoder.out if color not in pn_swap else ~encoder.out
                data_o = getattr(pads, f"data{channel}_{pol}")
                serializer = VideoHDMI10to1Serializer(
                    data_i       = {"p":data_i, "n": ~data_i}[pol],
                    data_o       = data_o,
                    clock_domain = clock_domain,
                )
                self.add_module(name=f"{color}_serializer_{pol}", module=serializer)

# HDMI (Gowin).

class VideoGowinHDMIPHY(LiteXModule):
    def __init__(self, pads, clock_domain="sys", pn_swap=[], true_lvds=False):
        self.sink = sink = stream.Endpoint(video_data_layout)

        # # #

        # Select OBUF primitive:
        # TLVDS_OBUF: for true LVDS pairs
        # ELVDS_OBUF: for emulated LVDS pairs
        obuf_type = {True: "TLVDS_OBUF", False:"ELVDS_OBUF"}[true_lvds]

        # Always ack Sink, no backpressure.
        self.comb += sink.ready.eq(1)

        # Clocking + Differential Signaling.
        pix_clk = ClockSignal(clock_domain)
        self.specials += Instance(obuf_type,
            i_I  = pix_clk if "clk" not in pn_swap else ~pix_clk,
            o_O  = pads.clk_p,
            o_OB = pads.clk_n,
        )

        for color, channel in _dvi_c2d.items():
            # TMDS Encoding.
            encoder = ClockDomainsRenamer(clock_domain)(TMDSEncoder())
            self.add_module(name=f"{color}_encoder", module=encoder)
            self.comb += encoder.d.eq(getattr(sink, color))
            self.comb += encoder.c.eq(Cat(sink.hsync, sink.vsync) if channel == 0 else 0)
            self.comb += encoder.de.eq(sink.de)

            # 10:1 Serialization + Differential Signaling.
            data_i = encoder.out if color not in pn_swap else ~encoder.out
            pad_o  = Signal()
            self.specials += Instance("OSER10",
                i_PCLK  = pix_clk,
                i_FCLK  = ClockSignal(clock_domain + "5x"),
                i_RESET = ResetSignal(clock_domain),
                **{f"i_D{i}" : data_i[i] for i in range(10)},
                o_Q     = pad_o,
            )

            self.specials += Instance(obuf_type,
                i_I  = pad_o,
                o_O  = getattr(pads, f"data{channel}_p"),
                o_OB = getattr(pads, f"data{channel}_n"),
            )


# HDMI (Xilinx Spartan6).

class VideoS6HDMIPHY(LiteXModule):
    def __init__(self, pads, clock_domain="sys"):
        self.sink = sink = stream.Endpoint(video_data_layout)

        # # #

        # Always ack Sink, no backpressure.
        self.comb += sink.ready.eq(1)

        # Clocking + Differential Signaling.
        pads_clk = Signal()
        self.specials += DDROutput(i1=1, i2=0, o=pads_clk, clk=ClockSignal(clock_domain))
        self.specials += Instance("OBUFDS", i_I=pads_clk, o_O=pads.clk_p, o_OB=pads.clk_n)

        # Encode/Serialize Datas.
        for color, channel in _dvi_c2d.items():

            # TMDS Encoding.
            encoder = ClockDomainsRenamer(clock_domain)(TMDSEncoder())
            self.add_module(name=f"{color}_encoder", module=encoder)
            self.comb += encoder.d.eq(getattr(sink, color))
            self.comb += encoder.c.eq(Cat(sink.hsync, sink.vsync) if channel == 0 else 0)
            self.comb += encoder.de.eq(sink.de)

            # 10:1 Serialization + Differential Signaling.
            pad_o = Signal()
            serializer = VideoHDMI10to1Serializer(
                data_i       = encoder.out,
                data_o       = pad_o,
                clock_domain = clock_domain,
            )
            self.add_module(name=f"{color}_serializer", module=serializer)
            pad_p = getattr(pads, f"data{channel}_p")
            pad_n = getattr(pads, f"data{channel}_n")
            self.specials += Instance("OBUFDS", i_I=pad_o, o_O=pad_p, o_OB=pad_n)

# HDMI (Xilinx 7-Series).

class VideoS7HDMI10to1Serializer(LiteXModule):
    def __init__(self, data_i, data_o, clock_domain):
        # Note: 2 OSERDESE2 are coupled for 10:1 Serialization (8:1 Max with one).

        # Map Input Data to OSERDESE2 Master/Slave.
        data_m = Signal(8)
        data_s = Signal(8)
        self.comb += data_m[0:8].eq(data_i[:8]) # D1 to D8
        self.comb += data_s[2:4].eq(data_i[8:]) # D3 to D4

        # OSERDESE2 Master/Slave.
        shift = Signal(2)
        for data, serdes in zip([data_m, data_s], ["master", "slave"]):
            self.specials += Instance("OSERDESE2",
                # Parameters
                p_DATA_WIDTH     = 10,
                p_TRISTATE_WIDTH = 1,
                p_DATA_RATE_OQ   = "DDR",
                p_DATA_RATE_TQ   = "DDR",
                p_SERDES_MODE    = serdes.upper(),

                # Controls.
                i_OCE    = 1,
                i_TCE    = 0,
                i_RST    = ResetSignal(clock_domain),
                i_CLK    = ClockSignal(clock_domain + "5x"),
                i_CLKDIV = ClockSignal(clock_domain),

                # Datas.
                **{f"i_D{n+1}": data[n] for n in range(8)},

                # Master/Slave shift in/out.
                i_SHIFTIN1  = shift[0] if serdes == "master" else 0,
                i_SHIFTIN2  = shift[1] if serdes == "master" else 0,
                o_SHIFTOUT1 = shift[0] if serdes == "slave"  else Open(),
                o_SHIFTOUT2 = shift[1] if serdes == "slave"  else Open(),

                # Output
                o_OQ = data_o if serdes == "master" else Open(),
            )


class VideoS7HDMIPHY(LiteXModule):
    def __init__(self, pads, clock_domain="sys"):
        self.sink = sink = stream.Endpoint(video_data_layout)

        # # #

        # Always ack Sink, no backpressure.
        self.comb += sink.ready.eq(1)

        # Clocking + Differential Signaling.
        pads_clk = Signal()
        self.specials += DDROutput(i1=1, i2=0, o=pads_clk, clk=ClockSignal(clock_domain))
        self.specials += Instance("OBUFDS", i_I=pads_clk, o_O=pads.clk_p, o_OB=pads.clk_n)

        # Encode/Serialize Datas.
        for color, channel in _dvi_c2d.items():

            # TMDS Encoding.
            encoder = ClockDomainsRenamer(clock_domain)(TMDSEncoder())
            self.submodules += encoder
            self.comb += encoder.d.eq(getattr(sink, color))
            self.comb += encoder.c.eq(Cat(sink.hsync, sink.vsync) if channel == 0 else 0)
            self.comb += encoder.de.eq(sink.de)

            # 10:1 Serialization + Differential Signaling.
            pad_o = Signal()
            serializer = VideoS7HDMI10to1Serializer(
                data_i       = encoder.out,
                data_o       = pad_o,
                clock_domain = clock_domain,
            )
            self.submodules += serializer
            pad_p = getattr(pads, f"data{channel}_p")
            pad_n = getattr(pads, f"data{channel}_n")
            self.specials += Instance("OBUFDS", i_I=pad_o, o_O=pad_p, o_OB=pad_n)


class VideoS7GTPHDMIPHY(LiteXModule):
    def __init__(self, pads, sys_clk_freq, clock_domain="sys", clk_freq=148.5e6, refclk=None):
        assert sys_clk_freq >= clk_freq
        self.sink = sink = stream.Endpoint(video_data_layout)

        # # #

        from liteiclink.serdes.gtp_7series import GTPQuadPLL, GTP

        # Always ack Sink, no backpressure.
        self.comb += sink.ready.eq(1)

        # Clocking + Differential Signaling.
        pads_clk = Signal()
        self.specials += DDROutput(i1=1, i2=0, o=pads_clk, clk=ClockSignal(clock_domain))
        self.specials += Instance("OBUFDS", i_I=pads_clk, o_O=pads.clk_p, o_OB=pads.clk_n)

        # GTP Quad PLL.
        if refclk is None:
            # No RefClk provided, use the Video Clk as GTP RefClk.
            refclk = ClockSignal(clock_domain)
        elif isinstance(refclk, Record):
            # Differential RefCLk provided, add an IBUFDS_GTE2.
            refclk_se = Signal()
            self.specials += Instance("IBUFDS_GTE2",
                i_CEB = 0,
                i_I   = refclk.p,
                i_IB  = refclk.n,
                o_O   = refclk_se
            )
            refclk = refclk_se
        self.pll = pll = GTPQuadPLL(refclk, clk_freq, 1.485e9)

        # Encode/Serialize Datas.
        for color, channel in _dvi_c2d.items():
            # TMDS Encoding.
            encoder = ClockDomainsRenamer(clock_domain)(TMDSEncoder())
            self.submodules += encoder
            self.comb += encoder.d.eq(getattr(sink, color))
            self.comb += encoder.c.eq(Cat(sink.hsync, sink.vsync) if channel == 0 else 0)
            self.comb += encoder.de.eq(sink.de)

            # 10:20 (SerDes has a minimal 20:1 Serialization ratio).
            converter = ClockDomainsRenamer(clock_domain)(stream.Converter(10, 20))
            self.submodules += converter
            self.comb += converter.sink.valid.eq(1)
            self.comb += converter.sink.data.eq(encoder.out)

            # Clock Domain Crossing (video_clk --> gtp_tx)
            cdc = stream.ClockDomainCrossing([("data", 20)], cd_from=clock_domain, cd_to=f"gtp{color}_tx")
            self.submodules += cdc
            self.comb += converter.source.connect(cdc.sink)
            self.comb += cdc.source.ready.eq(1) # No backpressure.

            # 20:1 Serialization + Differential Signaling.
            class GTPPads:
                def __init__(self, p, n):
                    self.p = p
                    self.n = n
            tx_pads = GTPPads(p=getattr(pads, f"data{channel}_p"), n=getattr(pads, f"data{channel}_n"))
            # FIXME: Find a way to avoid RX pads.
            rx_pads = GTPPads(p=getattr(pads, f"rx{channel}_p"),    n=getattr(pads, f"rx{channel}_n"))
            gtp = GTP(pll, tx_pads, rx_pads=rx_pads, sys_clk_freq=sys_clk_freq,
                tx_polarity      = 1, # FIXME: Specific to Decklink Mini 4K, make it configurable.
                tx_buffer_enable = True,
                rx_buffer_enable = True,
                clock_aligner    = False
            )
            setattr(self.submodules, f"gtp{color}", gtp)
            self.comb += gtp.tx_produce_pattern.eq(1)
            self.comb += gtp.tx_pattern.eq(cdc.source.data)
