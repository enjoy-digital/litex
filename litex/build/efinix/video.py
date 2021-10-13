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
    "1920x1080@50Hz": {
        "pix_clk"       : 148.5e6,
        "h_active"      : 1920,
        "h_blanking"    : 720,
        "h_sync_offset" : 528,
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

video_data_layout_dual = [
    # Synchronization signals.
    ("hsync", 2),
    ("vsync", 2),
    ("de",    2),
    # Data signals.
    ("r",     16),
    ("g",     16),
    ("b",     16),
]

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

class VideoLVDSPHY(Module):
    def __init__(self, platform, pads, pixel_clk='px_clk', px_clk_x3_5='px_clk_x3_5'):
        self.sink = sink = stream.Endpoint(video_data_layout_dual)

        # # #

        channel1 = Record(video_data_layout)
        channel2 = Record(video_data_layout)

        self.comb += [ channel1.r.eq(sink.r[0:8]),
                       channel1.g.eq(sink.g[0:8]),
                       channel1.b.eq(sink.b[0:8]),
                       channel1.de.eq(sink.de[0]),
                       channel1.vsync.eq(sink.vsync[0]),
                       channel1.hsync.eq(sink.hsync[0]),

                       channel2.r.eq(sink.r[7:16]),
                       channel2.g.eq(sink.g[7:16]),
                       channel2.b.eq(sink.b[7:16]),
                       channel2.de.eq(sink.de[1]),
                       channel2.vsync.eq(sink.vsync[1]),
                       channel2.hsync.eq(sink.hsync[1]),
        ]

        # Always ack Sink, no backpressure.
        self.comb += sink.ready.eq(1)

        # -------- LVDS CLOCK -----------

        name = platform.get_pin_name(pads.clk)
        pad = platform.get_pin_location(pads.clk)

        clk = platform.add_iface_io('hdmi_clk', 7)

        block = {'type':'LVDS',
                 'mode':'OUTPUT',
                 'name':name,
                 'location':[pad[0]],
                 'serialisation':7,
                 'fast_clk':px_clk_x3_5,
                 'slow_clk':pixel_clk,

        }
        platform.toolchain.ifacewriter.xml_blocks.append(block)
        platform.delete(pads.clk)

        # -------- LVDS DATA -----------

        lvds = []

        lvds.append((pads.rxpa1, platform.get_pin_name(pads.rxpa1), platform.get_pin_location(pads.rxpa1)))
        lvds.append((pads.rxpa2, platform.get_pin_name(pads.rxpa2), platform.get_pin_location(pads.rxpa2)))
        rxpa1 = platform.add_iface_io('hdmi_rxpa1', 7)
        rxpa2 = platform.add_iface_io('hdmi_rxpa2', 7)

        lvds.append((pads.rxpb1, platform.get_pin_name(pads.rxpb1), platform.get_pin_location(pads.rxpb1)))
        lvds.append((pads.rxpb2, platform.get_pin_name(pads.rxpb2), platform.get_pin_location(pads.rxpb2)))
        rxpb1 = platform.add_iface_io('hdmi_rxpb1', 7)
        rxpb2 = platform.add_iface_io('hdmi_rxpb2', 7)

        lvds.append((pads.rxpc1, platform.get_pin_name(pads.rxpc1), platform.get_pin_location(pads.rxpc1)))
        lvds.append((pads.rxpc2, platform.get_pin_name(pads.rxpc2), platform.get_pin_location(pads.rxpc2)))
        rxpc1 = platform.add_iface_io('hdmi_rxpc1', 7)
        rxpc2 = platform.add_iface_io('hdmi_rxpc2', 7)

        lvds.append((pads.rxpd1, platform.get_pin_name(pads.rxpd1), platform.get_pin_location(pads.rxpd1)))
        lvds.append((pads.rxpd2, platform.get_pin_name(pads.rxpd2), platform.get_pin_location(pads.rxpd2)))
        rxpd1 = platform.add_iface_io('hdmi_rxpd1', 7)
        rxpd2 = platform.add_iface_io('hdmi_rxpd2', 7)

        for signal, name, pad in lvds:
            block = {'type':'LVDS',
                    'mode':'OUTPUT',
                    'name':name,
                    'location':[pad[0]],
                    'serialisation':7,
                    'fast_clk':px_clk_x3_5,
                    'slow_clk':pixel_clk,

            }
            platform.toolchain.ifacewriter.xml_blocks.append(block)
            platform.delete(signal)

        self.comb += [ rxpa1.eq(Cat(channel1.g[2], channel1.r[7],  channel1.r[6],  channel1.r[5], channel1.r[4], channel1.r[3], channel1.r[2])),
                       rxpb1.eq(Cat(channel1.b[3], channel1.b[2],  channel1.g[7],  channel1.g[6], channel1.g[5], channel1.g[4], channel1.g[3])),
                       rxpc1.eq(Cat(channel1.de,   channel1.vsync, channel1.hsync, channel1.b[7], channel1.b[6], channel1.b[5], channel1.b[4])),
                       rxpd1.eq(Cat(0,             channel1.b[7],  channel1.b[7],  channel1.g[7], channel1.g[7], channel1.r[7], channel1.r[7])),

                       rxpa2.eq(Cat(channel2.g[2], channel2.r[7],  channel2.r[6],  channel2.r[5], channel2.r[4], channel2.r[3], channel2.r[2])),
                       rxpb2.eq(Cat(channel2.b[3], channel2.b[2],  channel2.g[7],  channel2.g[6], channel2.g[5], channel2.g[4], channel2.g[3])),
                       rxpc2.eq(Cat(channel2.de,   channel2.vsync, channel2.hsync, channel2.b[7], channel2.b[6], channel2.b[5], channel2.b[4])),
                       rxpd2.eq(Cat(0,             channel2.b[7],  channel2.b[7],  channel2.g[7], channel2.g[7], channel2.r[7], channel2.r[7])),

                       clk.eq(0b1100011),
        ]
