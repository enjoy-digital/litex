import os

from migen import *

from litex.soc.interconnect import wishbone

class usbkbd( Module ):
    def __init__( self, platform, pads, clk_freq ):
        self.bus = wishbone.Interface()
        self.pads = pads
        self.specials += Instance(
            "wishbone_usbkbd",
            i_RST_I = ResetSignal(),
            i_CLK_I = ClockSignal(),
            i_ADR_I = self.bus.adr,
            i_DAT_I = self.bus.dat_w,
            o_DAT_O = self.bus.dat_r,
            i_WE_I = self.bus.we,
            i_SEL_I = self.bus.sel,
            i_STB_I = self.bus.stb,
            o_ACK_O = self.bus.ack,
            i_CYC_I = self.bus.cyc,
            io_dp = pads.dp,
            io_dn = pads.dn,
            p_CLK_FREQ = clk_freq )
        platform.add_source( os.path.join( os.path.dirname( __file__ ),
                                           "usbkbd.v" ) )
