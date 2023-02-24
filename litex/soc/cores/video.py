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

class VideoTimingGenerator(Module, AutoCSR):
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
        self._enable      = CSRStorage(reset=1)

        self._hres        = CSRStorage(hbits, vt["h_active"])
        self._hsync_start = CSRStorage(hbits, vt["h_active"] + vt["h_sync_offset"])
        self._hsync_end   = CSRStorage(hbits, vt["h_active"] + vt["h_sync_offset"] + vt["h_sync_width"])
        self._hscan       = CSRStorage(hbits, vt["h_active"] + vt["h_blanking"] - 1)

        self._vres        = CSRStorage(vbits, vt["v_active"])
        self._vsync_start = CSRStorage(vbits, vt["v_active"] + vt["v_sync_offset"])
        self._vsync_end   = CSRStorage(vbits, vt["v_active"] + vt["v_sync_offset"] + vt["v_sync_width"])
        self._vscan       = CSRStorage(vbits, vt["v_active"] + vt["v_blanking"] - 1)

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
        self.submodules.fsm = fsm
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

class ColorBarsPattern(Module):
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
        self.submodules.fsm = fsm
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

class CSIInterpreter(Module):
    # FIXME: Very basic/minimal implementation for now.
    esc_start     = 0x1b
    csi_start     = ord("[")
    csi_param_min = 0x30
    csi_param_max = 0x3f
    def __init__(self, enable=True):
        self.sink   = sink   = stream.Endpoint([("data", 8)])
        self.source = source = stream.Endpoint([("data", 8)])

        self.color    = Signal(4)
        self.clear_xy = Signal()

        # # #

        if not enable:
            self.comb += self.sink.connect(self.source)
            return

        csi_count = Signal(3)
        csi_bytes = Array([Signal(8) for _ in range(8)])
        csi_final = Signal(8)

        self.submodules.fsm = fsm = FSM(reset_state="RECOPY")
        fsm.act("RECOPY",
            sink.connect(source),
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
                If((csi_bytes[0] == ord("9")) and (csi_bytes[1] == ord("2")),
                    NextValue(self.color, 1), # FIXME: Add Palette.
                ).Else(
                    NextValue(self.color, 0), # FIXME: Add Palette.
                ),
            ),
            If(csi_final == ord("A"), # FIXME: Move Up.
                self.clear_xy.eq(1)
            ),
            NextState("RECOPY")
        )

class VideoTerminal(Module):
    def __init__(self, hres=800, vres=600, with_csi_interpreter=True):
        self.enable    = Signal(reset=1)
        self.vtg_sink  = vtg_sink   = stream.Endpoint(video_timing_layout)
        self.uart_sink = uart_sink  = stream.Endpoint([("data", 8)])
        self.source    = source     = stream.Endpoint(video_data_layout)

        # # #

        csi_width = 8 if with_csi_interpreter else 0

        # Font Mem.
        # ---------
        # FIXME: Store Font in LiteX?
        if not os.path.exists("ter-u16b.bdf"):
            os.system("wget https://github.com/enjoy-digital/litex/files/6076336/ter-u16b.txt")
            os.system("mv ter-u16b.txt ter-u16b.bdf")
        font        = import_bdf_font("ter-u16b.bdf")
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

        # UART Terminal Fill.
        # -------------------

        # Optional CSI Interpreter.
        self.submodules.csi_interpreter = CSIInterpreter(enable=with_csi_interpreter)
        self.comb += uart_sink.connect(self.csi_interpreter.sink)
        uart_sink = self.csi_interpreter.source
        self.comb += term_wrport.dat_w[font_width:].eq(self.csi_interpreter.color)

        self.submodules.uart_fifo = stream.SyncFIFO([("data", 8)], 8)
        self.comb += uart_sink.connect(self.uart_fifo.sink)
        uart_sink = self.uart_fifo.source

        # UART Reception and Terminal Fill.
        x_term = term_wrport.adr[:7]
        y_term = term_wrport.adr[7:]
        y_term_rollover = Signal()
        self.submodules.uart_fsm = uart_fsm = FSM(reset_state="RESET")
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
        uart_fsm.act("IDLE",
            If(uart_sink.valid,
                If(uart_sink.data == ord("\n"),
                    uart_sink.ready.eq(1), # Ack sink.
                    NextState("INCR-Y")
                ).Elif(uart_sink.data == ord("\r"),
                    uart_sink.ready.eq(1), # Ack sink.
                    NextState("RST-X")
                ).Else(
                    NextState("WRITE")
                )
            ),
            If(self.csi_interpreter.clear_xy,
                NextState("CLEAR-XY")
            )
        )
        uart_fsm.act("WRITE",
            uart_sink.ready.eq(1),
            term_wrport.we.eq(1),
            term_wrport.dat_w[:font_width].eq(uart_sink.data),
            NextState("INCR-X")
        )
        uart_fsm.act("RST-X",
            NextValue(x_term, 0),
            NextState("CLEAR-X")
        )
        uart_fsm.act("INCR-X",
            NextValue(x_term, x_term + 1),
            NextState("IDLE"),
            If(x_term == (80 - 1),
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
            If((x >= 80) | (y >= term_lines),
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
        # FIXME: Add Palette.
        self.comb += [
            If(bit,
                Case(term_rdport.dat_r[font_width:], {
                    0: [Cat(source.r, source.g, source.b).eq(0xffffff)],
                    1: [Cat(source.r, source.g, source.b).eq(0x89e234)],
                })
            ).Else(
                Cat(source.r, source.g, source.b).eq(0x000000),
            )
        ]

# Video FrameBuffer --------------------------------------------------------------------------------

class VideoFrameBuffer(Module, AutoCSR):
    """Video FrameBuffer"""
    def __init__(self, dram_port, hres=800, vres=600, base=0x00000000, fifo_depth=65536, clock_domain="sys", clock_faster_than_sys=False, format="rgb888"):
        self.vtg_sink  = vtg_sink = stream.Endpoint(video_timing_layout)
        self.source    = source   = stream.Endpoint(video_data_layout)
        self.underflow = Signal()

        self.depth = depth = {
            "rgb888" : 32,
            "rgb565" : 16
        }[format]

        # # #

        # Video DMA.
        from litedram.frontend.dma import LiteDRAMDMAReader
        self.submodules.dma = LiteDRAMDMAReader(dram_port, fifo_depth=fifo_depth//(dram_port.data_width//8), fifo_buffered=True)
        self.dma.add_csr(
            default_base   = base,
            default_length = hres*vres*depth//8, # 32-bit RGB-888 or 16-bit RGB-565
            default_enable = 0,
            default_loop   = 1
        )

        # If DRAM Data Width > depth and Video clock is faster than sys_clk:
        if (dram_port.data_width > depth) and clock_faster_than_sys:
            # Do Clock Domain Crossing first...
            self.submodules.cdc = stream.ClockDomainCrossing([("data", dram_port.data_width)], cd_from="sys", cd_to=clock_domain)
            self.comb += self.dma.source.connect(self.cdc.sink)
            # ... and then Data-Width Conversion.
            self.submodules.conv = ClockDomainsRenamer(clock_domain)(stream.Converter(dram_port.data_width, depth))
            self.comb += self.cdc.source.connect(self.conv.sink)
            video_pipe_source = self.conv.source
        # Elsif DRAM Data Width <= depth or Video clock is slower than sys_clk:
        else:
            # Do Data-Width Conversion first...
            self.submodules.conv = stream.Converter(dram_port.data_width, depth)
            self.comb += self.dma.source.connect(self.conv.sink)
            # ... and then Clock Domain Crossing.
            self.submodules.cdc = stream.ClockDomainCrossing([("data", depth)], cd_from="sys", cd_to=clock_domain)
            self.comb += self.conv.source.connect(self.cdc.sink)
            if (dram_port.data_width < depth) and (depth == 32): # FIXME.
                self.comb += [
                    self.cdc.sink.data[ 0: 8].eq(self.conv.source.data[16:24]),
                    self.cdc.sink.data[16:24].eq(self.conv.source.data[ 0: 8]),
                ]
            video_pipe_source = self.cdc.source

        # Video Generation.
        self.comb += [
            vtg_sink.ready.eq(1),
            If(vtg_sink.valid & vtg_sink.de,
                video_pipe_source.connect(source, keep={"valid", "ready"}),
                vtg_sink.ready.eq(source.valid & source.ready),

            ),
            vtg_sink.connect(source, keep={"de", "hsync", "vsync"}),
        ]
        if (depth == 32):
            self.comb += [
               source.r.eq(video_pipe_source.data[ 0: 8]),
               source.g.eq(video_pipe_source.data[ 8:16]),
               source.b.eq(video_pipe_source.data[16:24]),
            ]
        else: # depth == 16
            self.comb += [
                source.r.eq(Cat(Signal(3, reset = 0), video_pipe_source.data[11:16])),
                source.g.eq(Cat(Signal(2, reset = 0), video_pipe_source.data[ 5:11])),
                source.b.eq(Cat(Signal(3, reset = 0), video_pipe_source.data[ 0: 5])),
            ]

        # Underflow.
        self.comb += self.underflow.eq(~source.valid)

# Video PHYs ---------------------------------------------------------------------------------------

# Generic (Very Generic PHY supporting VGA/DVI and variations).

class VideoGenericPHY(Module):
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

class VideoHDMI10to1Serializer(Module):
    def __init__(self, data_i, data_o, clock_domain):
        # Clock Domain Crossing.
        self.submodules.cdc = stream.ClockDomainCrossing([("data", 10)], cd_from=clock_domain, cd_to=clock_domain + "5x")
        self.comb += self.cdc.sink.valid.eq(1)
        self.comb += self.cdc.sink.data.eq(data_i)

        # 10:2 Gearbox.
        self.submodules.gearbox = ClockDomainsRenamer(clock_domain + "5x")(stream.Gearbox(i_dw=10, o_dw=2, msb_first=False))
        self.comb += self.cdc.source.connect(self.gearbox.sink)

        # 2:1 Output DDR.
        self.comb += self.gearbox.source.ready.eq(1)
        self.specials += DDROutput(
            clk = ClockSignal(clock_domain + "5x"),
            i1  = self.gearbox.source.data[0],
            i2  = self.gearbox.source.data[1],
            o   = data_o,
        )

class VideoHDMIPHY(Module):
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
                setattr(self.submodules, f"{color}_encoder", encoder)
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
                setattr(self.submodules, f"{color}_serializer", serializer)

# HDMI (Gowin).

class VideoGowinHDMIPHY(Module):
    def __init__(self, pads, clock_domain="sys", pn_swap=[]):
        self.sink = sink = stream.Endpoint(video_data_layout)

        # # #

        # Always ack Sink, no backpressure.
        self.comb += sink.ready.eq(1)

        # Clocking + Differential Signaling.
        pix_clk = ClockSignal(clock_domain)
        self.specials += Instance("ELVDS_OBUF",
            i_I  = pix_clk if "clk" not in pn_swap else ~pix_clk,
            o_O  = pads.clk_p,
            o_OB = pads.clk_n,
        )

        for color, channel in _dvi_c2d.items():
            # TMDS Encoding.
            encoder = ClockDomainsRenamer(clock_domain)(TMDSEncoder())
            setattr(self.submodules, f"{color}_encoder", encoder)
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

            self.specials += Instance("ELVDS_OBUF",
                i_I  = pad_o,
                o_O  = getattr(pads, f"data{channel}_p"),
                o_OB = getattr(pads, f"data{channel}_n"),
            )


# HDMI (Xilinx Spartan6).

class VideoS6HDMIPHY(Module):
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
            setattr(self.submodules, f"{color}_encoder", encoder)
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
            setattr(self.submodules, f"{color}_serializer", serializer)
            pad_p = getattr(pads, f"data{channel}_p")
            pad_n = getattr(pads, f"data{channel}_n")
            self.specials += Instance("OBUFDS", i_I=pad_o, o_O=pad_p, o_OB=pad_n)

# HDMI (Xilinx 7-Series).

class VideoS7HDMI10to1Serializer(Module):
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
                o_SHIFTOUT1 = shift[0] if serdes == "slave"  else 0,
                o_SHIFTOUT2 = shift[1] if serdes == "slave"  else 0,

                # Output
                o_OQ = data_o if serdes == "master" else Open(),
            )


class VideoS7HDMIPHY(Module):
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


class VideoS7GTPHDMIPHY(Module):
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
        self.submodules.pll = pll = GTPQuadPLL(refclk, clk_freq, 1.485e9)

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
