import os

from migen import *

from litex.soc.interconnect import wishbone


class VexRiscv(Module):
    def __init__(self, platform, cpu_reset_address):
        self.ibus = i = wishbone.Interface()
        self.dbus = d = wishbone.Interface()

        self.interrupt = Signal(32)

        self.specials += Instance("VexRiscv",
                                  i_clk=ClockSignal(),
                                  i_reset=ResetSignal(),

                                  i_externalResetVector=cpu_reset_address,
                                  i_externalInterruptArray=self.interrupt,
                                  i_timerInterrupt=0,

                                  o_iBusWishbone_ADR=i.adr,
                                  o_iBusWishbone_DAT_MOSI=i.dat_w,
                                  o_iBusWishbone_SEL=i.sel,
                                  o_iBusWishbone_CYC=i.cyc,
                                  o_iBusWishbone_STB=i.stb,
                                  o_iBusWishbone_WE=i.we,
                                  o_iBusWishbone_CTI=i.cti,
                                  o_iBusWishbone_BTE=i.bte,
                                  i_iBusWishbone_DAT_MISO=i.dat_r,
                                  i_iBusWishbone_ACK=i.ack,
                                  i_iBusWishbone_ERR=i.err,

                                  o_dBusWishbone_ADR=d.adr,
                                  o_dBusWishbone_DAT_MOSI=d.dat_w,
                                  o_dBusWishbone_SEL=d.sel,
                                  o_dBusWishbone_CYC=d.cyc,
                                  o_dBusWishbone_STB=d.stb,
                                  o_dBusWishbone_WE=d.we,
                                  o_dBusWishbone_CTI=d.cti,
                                  o_dBusWishbone_BTE=d.bte,
                                  i_dBusWishbone_DAT_MISO=d.dat_r,
                                  i_dBusWishbone_ACK=d.ack,
                                  i_dBusWishbone_ERR=d.err)

        # add verilog sources
        self.add_sources(platform)

    @staticmethod
    def add_sources(platform):
        vdir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "verilog")
        platform.add_sources(os.path.join(vdir), "VexRiscv.v")
        platform.add_verilog_include_path(vdir)
