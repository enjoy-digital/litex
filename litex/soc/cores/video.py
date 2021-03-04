#
# This file is part of LiteX.
#
# Copyright (c) 2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import math

from migen import *
from migen.genlib.cdc import MultiReg

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import stream

# Video Constants ----------------------------------------------------------------------------------

hbits = 12
vbits = 12

# Video Timings ------------------------------------------------------------------------------------

video_timings = {
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
        "pix_clk"       : 148.35e6,
        "h_active"      : 1920,
        "h_blanking"    : 280,
        "h_sync_offset" : 88,
        "h_sync_width"  : 44,
        "v_active"      : 1080,
        "v_blanking"    : 45,
        "v_sync_offset" : 4,
        "v_sync_width"  : 5,
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

class VideoTimingGenerator(Module, AutoCSR):
    def __init__(self, default_video_timings="800x600@60Hz"):
        vt = video_timings[default_video_timings]
        # MMAP Control/Status Registers.
        self._enable      = CSRStorage(reset=1)

        self._hres        = CSRStorage(hbits, vt["h_active"])
        self._hsync_start = CSRStorage(hbits, vt["h_active"] + vt["h_sync_offset"])
        self._hsync_end   = CSRStorage(hbits, vt["h_active"] + vt["h_sync_offset"] + vt["h_sync_width"])
        self._hscan       = CSRStorage(hbits, vt["h_active"] + vt["h_blanking"])

        self._vres        = CSRStorage(vbits, vt["v_active"])
        self._vsync_start = CSRStorage(vbits, vt["v_active"] + vt["v_sync_offset"])
        self._vsync_end   = CSRStorage(vbits, vt["v_active"] + vt["v_sync_offset"] + vt["v_sync_width"])
        self._vscan       = CSRStorage(vbits, vt["v_active"] + vt["v_blanking"])

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
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            NextValue(hactive, 0),
            NextValue(vactive, 0),
            NextValue(source.hres, hres),
            NextValue(source.vres, vres),
            NextValue(source.hcount,  0),
            NextValue(source.vcount,  0),
            If(enable,
                NextState("RUN")
            )
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
                If(source.hcount == 0,           NextValue(hactive,      1)), # Start of HActive.
                If(source.hcount == hres,        NextValue(hactive,      0)), # End of HActive.
                If(source.hcount == hsync_start, NextValue(source.hsync, 1)), # Start of HSync.
                If(source.hcount == hsync_end,   NextValue(source.hsync, 0)), # End of HSync.
                # End of HScan.
                If(source.hcount == hscan,
                    # Reset HCount.
                    NextValue(source.hcount, 0),
                    # Increment VCount.
                    NextValue(source.vcount, source.vcount + 1),
                    # Generate VActive / VSync.
                    If(source.vcount == 0,           NextValue(vactive,      1)), # Start of VActive.
                    If(source.vcount == vres,        NextValue(vactive,      0)), # End of HActive.
                    If(source.vcount == vsync_start, NextValue(source.vsync, 1)), # Start of VSync.
                    If(source.vcount == vsync_end,   NextValue(source.vsync, 0)), # End of VSync.
                    # End of VScan.
                    If(source.vcount == vscan,
                        # Reset VCount.
                        NextValue(source.vcount, 0),
                    )
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
    def __init__(self):
        self.sink   = sink   = stream.Endpoint([("data", 8)])
        self.source = source = stream.Endpoint([("data", 8)])

        self.color = Record([("r", 8), ("g", 8), ("b", 8)])
        self.color.r.reset = 0xff
        self.color.g.reset = 0xff
        self.color.b.reset = 0xff

        # # #

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
                # FIXME: Write color in Terminal Mem.
                If((csi_bytes[0] == ord("9")) and (csi_bytes[1] == ord("2")),
                    NextValue(self.color.r, 0x89),
                    NextValue(self.color.g, 0xe2),
                    NextValue(self.color.b, 0x34),
                ).Else(
                    NextValue(self.color.r, self.color.r.reset),
                    NextValue(self.color.g, self.color.g.reset),
                    NextValue(self.color.b, self.color.b.reset),
                ),
            ),
            NextState("RECOPY")
        )

class VideoTerminal(Module):
    def __init__(self, hres=640, vres=480, with_csi_interpreter=True):
        self.enable    = Signal(reset=1)
        self.vtg_sink  = vtg_sink   = stream.Endpoint(video_timing_layout)
        self.uart_sink = uart_sink  = stream.Endpoint([("data", 8)])
        self.source    = source     = stream.Endpoint(video_data_layout)

        # # #

        # Font Mem.
        # ---------
        os.system("wget https://github.com/enjoy-digital/litex/files/6076336/ter-u16b.txt") # FIXME: Store Font in LiteX?
        os.system("mv ter-u16b.txt ter-u16b.bdf")
        font        = import_bdf_font("ter-u16b.bdf")
        font_width  = 8
        font_heigth = 16
        font_mem    = Memory(width=8, depth=4096, init=font)
        font_rdport = font_mem.get_port(write_capable=False, has_re=True)
        self.specials += font_mem, font_rdport

        # Terminal Mem.
        # -------------
        term_colums = 128 # 80 rounded to next power of two.
        term_lines  = math.floor(vres/font_heigth)
        term_depth  = term_colums * term_lines
        term_init   = [ord(c) for c in [" "]*term_colums*term_lines]
        term_mem    = Memory(width=font_width, depth=term_depth, init=term_init)
        term_wrport = term_mem.get_port(write_capable=True)
        term_rdport = term_mem.get_port(write_capable=False, has_re=True)
        self.specials += term_mem, term_wrport, term_rdport

        # UART Terminal Fill.
        # -------------------

        # Optional CSI Interpreter.
        if with_csi_interpreter:
            self.submodules.csi_interpreter = CSIInterpreter()
            self.comb += uart_sink.connect(self.csi_interpreter.sink)
            uart_sink = self.csi_interpreter.source

        self.submodules.uart_fifo = stream.SyncFIFO([("data", 8)], 8)
        self.comb += uart_sink.connect(self.uart_fifo.sink)
        uart_sink = self.uart_fifo.source

        # UART Reception and Terminal Fill.
        x_term = term_wrport.adr[:7]
        y_term = term_wrport.adr[7:]
        y_term_rollover = Signal()
        self.submodules.uart_fsm = uart_fsm = FSM(reset_state="IDLE")
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
            )
        )
        uart_fsm.act("WRITE",
            uart_sink.ready.eq(1),
            term_wrport.we.eq(1),
            term_wrport.dat_w.eq(uart_sink.data),
            NextState("INCR-X")
        )
        uart_fsm.act("RST-X",
            NextValue(x_term, 0),
            NextState("IDLE")
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
            term_wrport.dat_w.eq(ord(" ")),
            If(x_term == (80 - 1),
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
            term_dat_r.eq(term_rdport.dat_r),
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
        # FIXME: Allow static/dynamic Font color.
        self.comb += If(bit,
            source.r.eq(0xff),
            source.g.eq(0xff),
            source.b.eq(0xff),
        ).Else(
            source.r.eq(0x00),
            source.g.eq(0x00),
            source.b.eq(0x00)
        )

# Video FrameBuffer --------------------------------------------------------------------------------

class VideoFrameBuffer(Module, AutoCSR):
    """Video FrameBuffer"""
    def __init__(self, dram_port, hres=640, vres=480, base=0x00000000, clock_domain="sys"):
        self.vtg_sink = vtg_sink   = stream.Endpoint(video_timing_layout)
        self.source   = source = stream.Endpoint(video_data_layout)

        # # #

        # Video DMA.
        from litedram.frontend.dma import LiteDRAMDMAReader
        self.submodules.dma = LiteDRAMDMAReader(dram_port, fifo_depth=2048, fifo_buffered=True) # FIXME: Adjust/Expose.
        self.dma.add_csr(
            default_base   = base,
            default_length = hres*vres*32//8, # 32-bit RGB-444
            default_start  = 1,
            default_loop   = 1
        )

        # FIXME: Make sure it will work for all DRAM's data-width/all Video resolutions.

        # Video Data-Width Converter.
        self.submodules.conv = stream.Converter(dram_port.data_width, 32)
        self.comb += self.dma.source.connect(self.conv.sink)

        # Video CDC.
        self.submodules.cdc = stream.ClockDomainCrossing([("data", 32)], cd_from="sys", cd_to=clock_domain)
        self.comb += self.conv.source.connect(self.cdc.sink)

        # Video Generation.
        self.comb += [
            vtg_sink.ready.eq(1),
            If(vtg_sink.valid & vtg_sink.de,
                source.valid.eq(self.cdc.source.valid),
                vtg_sink.ready.eq(source.ready),
                self.cdc.source.ready.eq(source.ready)
            ),
            source.de.eq(vtg_sink.de),
            source.hsync.eq(vtg_sink.hsync),
            source.vsync.eq(vtg_sink.vsync),
            source.r.eq(self.cdc.source.data[ 0: 8]),
            source.g.eq(self.cdc.source.data[ 8:16]),
            source.b.eq(self.cdc.source.data[16:24]),
        ]

# Video PHYs ---------------------------------------------------------------------------------------

class VideoDVIPHY(Module):
    def __init__(self, pads, clock_domain="sys"):
        self.sink = sink = stream.Endpoint(video_data_layout)

        # # #

        # FIXME: Use IOs primitives.

        self.comb += [
            # Always ack Sink, no backpressure.
            sink.ready.eq(1),

            # Drive DVI Clk.
            pads.clk.eq(ClockSignal(clock_domain)),

            # Drive DVI Controls.
            pads.de.eq(sink.de),
            pads.hsync.eq(sink.hsync),
            pads.vsync.eq(sink.vsync),

            # Drive DVI Datas.
            pads.r.eq(sink.r[8-len(pads.r):]),
            pads.g.eq(sink.g[8-len(pads.g):]),
            pads.b.eq(sink.b[8-len(pads.b):]),
        ]


class VideoVGAPHY(Module):
    def __init__(self, pads, clock_domain="sys"):
        self.sink = sink = stream.Endpoint(video_data_layout)

        # # #

        # FIXME: Use IOs primitives.

        self.comb += [
            # Always ack Sink, no backpressure.
            sink.ready.eq(1),

            # Drive DVI Controls.
            pads.hsync_n.eq(~sink.hsync),
            pads.vsync_n.eq(~sink.vsync),

            # Drive DVI Datas.
            pads.r.eq(sink.r[8-len(pads.r):]),
            pads.g.eq(sink.g[8-len(pads.g):]),
            pads.b.eq(sink.b[8-len(pads.b):]),
        ]
