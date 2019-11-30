#!/usr/bin/env python3

# This file is Copyright (c) 2019 Frank Buss <fb@frank-buss.de>
# License: BSD

import os
from migen import *
from litex.soc.interconnect import wishbone

# Terminal emulation with 640 x 480 pixels, 80 x 30 characters,
# individual foreground and background color per character (VGA palette)
# and user definable font, with code page 437 VGA font initialized.
# 60 Hz framerate, if clk is 25.175 MHz. Independent system clock possible,
# internal dual-port block RAM.
#
# Memory layout:
# 0x0000 - 0x12bf = 2 bytes per character:
#    character: index in VGA font
#    color: low nibble is foreground color, and high nibble is background color, VGA palette
# 0x12c0 - 0x22bf = VGA font, 16 lines per character, 8 bits width
#
# VGA timings:
# clocks per line:
# 1. HSync low pulse for 96 clocks
# 2. back porch for 48 clocks
# 3. data for 640 clocks
# 4. front porch for 16 clocks
#
# VSync timing per picture (800 clocks = 1 line):
# 1. VSync low pulse for 2 lines
# 2. back porch for 29 lines
# 3. data for 480 lines
# 4. front porch for 10 lines

# return filename relative to caller script, if available, otherwise relative to this package script
def get_path(filename):
    if os.path.isfile(filename):
        return filename
    path = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(path, filename)

# read file, if not empty, and test for size. If empty, init with 0
def read_ram_init_file(filename, size):
    if filename == '':
        return [0] * size
    else:
        with open(get_path(filename), "rb") as file:
            data = list(file.read())
        if len(data) != size:
            raise ValueError("Invalid size for file {}. Expected size: {}, actual size: {}".format(filename, size, len(data)))
        return data

# main class    
class Terminal(Module):
    def __init__(self, clk, font_filename = 'cp437.bin', screen_init_filename = 'screen-init.bin'):
        self.clock_domains.cd_clk = ClockDomain()
        self.comb += self.cd_clk.clk.eq(clk)

        # Wishbone interface
        self.bus = bus = wishbone.Interface(data_width = 8)

        # acknowledge immediately
        self.sync += [
            bus.ack.eq(0),
            If (bus.cyc & bus.stb & ~bus.ack, bus.ack.eq(1))
        ]
        
        # RAM initialization
        screen_init = read_ram_init_file(screen_init_filename, 4800)
        font = read_ram_init_file(font_filename, 4096)
        ram_init = screen_init + font

        # create RAM
        self.mem = mem = Memory(width=8, depth=8896, init = ram_init)
        self.specials += mem
        wrport = mem.get_port(write_capable=True, clock_domain="sys")
        self.specials += wrport
        rdport = mem.get_port(write_capable=False, clock_domain="clk")
        self.specials += rdport

        # memory map internal block RAM to Wishbone interface
        self.sync += [
            wrport.we.eq(0),
            If (bus.cyc & bus.stb & bus.we,
                wrport.we.eq(1),
                wrport.adr.eq(bus.adr),
                wrport.dat_w.eq(bus.dat_w),
            )
        ]

        # display resolution
        WIDTH = 640
        HEIGHT = 480

        # offset to font data in RAM
        FONT_ADDR = 80 * 30 * 2

        # VGA output
        self.red = red = Signal(8)
        self.green = green = Signal(8)
        self.blue = blue = Signal(8)
        self.vga_hsync = vga_hsync = Signal()
        self.vga_vsync = vga_vsync = Signal()

        # CPU interface
        self.vsync = vsync = Signal()
        
        H_SYNC_PULSE = 96
        H_BACK_PORCH = 48 + H_SYNC_PULSE
        H_DATA = WIDTH + H_BACK_PORCH
        H_FRONT_PORCH = 16 + H_DATA

        V_SYNC_PULSE = 2
        V_BACK_PORCH = 29 + V_SYNC_PULSE
        V_DATA = HEIGHT + V_BACK_PORCH
        V_FRONT_PORCH = 10 + V_DATA

        pixel_counter = Signal(10)
        line_counter = Signal(10)

        # read address in text RAM
        self.text_addr = text_addr = Signal(16)
        
        # read address in text RAM at line start
        self.text_addr_start = text_addr_start = Signal(16)
        
        # current line within a character, 0 to 15
        self.fline = fline = Signal(4)

        # current x position within a character, 0 to 7
        self.fx = fx = Signal(3)

        # current and next byte for a character line
        fbyte = Signal(8)
        next_byte = Signal(8)

        # current foreground color
        fgcolor = Signal(24)
        next_fgcolor = Signal(24)
        
        # current background color
        bgcolor = Signal(24)

        # current fg/bg color index from RAM
        color = Signal(8)

        # color index and lookup
        color_index = Signal(4)
        color_lookup = Signal(24)

        # VGA palette
        palette = [
            0x000000, 0x0000AA, 0x00AA00, 0x00AAAA, 0xAA0000, 0xAA00AA, 0xAA5500, 0xAAAAAA,
            0x555555, 0x5555FF, 0x55FF55, 0x55FFFF, 0xFF5555, 0xFF55FF, 0xFFFF55, 0xFFFFFF
        ]
        cases = {}
        for i in range(16):
            cases[i] = color_lookup.eq(palette[i])
        self.comb += Case(color_index, cases)

        self.sync.clk += [
            # default values
            red.eq(0),
            green.eq(0),
            blue.eq(0),
            
            # show pixels
            If ((line_counter >= V_BACK_PORCH) & (line_counter < V_DATA),
                If ((pixel_counter >= H_BACK_PORCH) & (pixel_counter < H_DATA),
                    If (fbyte[7],
                        red.eq(fgcolor[16:24]),
                        green.eq(fgcolor[8:16]),
                        blue.eq(fgcolor[0:8])
                    ).Else (
                        red.eq(bgcolor[16:24]),
                        green.eq(bgcolor[8:16]),
                        blue.eq(bgcolor[0:8])
                    ),
                    fbyte.eq(Cat(Signal(), fbyte[:-1]))
                )
            ),

            # load next character code, font line and color
            If (fx == 1,
                # schedule reading the character code
                rdport.adr.eq(text_addr),
                text_addr.eq(text_addr + 1)
            ),
            If (fx == 2,
                # schedule reading the color
                rdport.adr.eq(text_addr),
                text_addr.eq(text_addr + 1)
            ),
            If (fx == 3,
                # read character code, and set address for font line
                rdport.adr.eq(FONT_ADDR + Cat(Signal(4), rdport.dat_r) + fline)
            ),
            If (fx == 4,
                # read color
                color.eq(rdport.dat_r)
            ),
            If (fx == 5,
                # read font line, and set color index to get foreground color
                next_byte.eq(rdport.dat_r),
                color_index.eq(color[0:4]),
            ),
            If (fx == 6,
                # get next foreground color, and set color index for background color
                next_fgcolor.eq(color_lookup),
                color_index.eq(color[4:8])
            ),
            If (fx == 7,
                # set background color and everything for the next 8 pixels
                bgcolor.eq(color_lookup),
                fgcolor.eq(next_fgcolor),
                fbyte.eq(next_byte)
            ),
            fx.eq(fx + 1),
            If (fx == 7, fx.eq(0)),

            # horizontal timing for one line
            pixel_counter.eq(pixel_counter + 1),
            If (pixel_counter < H_SYNC_PULSE,
                vga_hsync.eq(0)
            ).Elif (pixel_counter < H_BACK_PORCH,
                vga_hsync.eq(1)
            ),
            If (pixel_counter == H_BACK_PORCH - 9,
                # prepare reading first character of next line
                fx.eq(0),
                text_addr.eq(text_addr_start)
            ),
            If (pixel_counter == H_FRONT_PORCH,
                # initilize next line
                pixel_counter.eq(0),
                line_counter.eq(line_counter + 1),

                # font height is 16 pixels
                fline.eq(fline + 1),
                If (fline == 15,
                    fline.eq(0),
                    text_addr_start.eq(text_addr_start + 2 * 80)
                )
            ),

            # vertical timing for one screen
            If (line_counter < V_SYNC_PULSE,
                vga_vsync.eq(0),
                vsync.eq(1)
            ).Elif (line_counter < V_BACK_PORCH,
                vga_vsync.eq(1),
                vsync.eq(0)
            ),
            If (line_counter == V_FRONT_PORCH,
                # end of image
                line_counter.eq(0)
            ),
            If (line_counter == V_BACK_PORCH - 1,
                # prepare generating next image data
                fline.eq(0),
                text_addr_start.eq(0)
            )
        ]
