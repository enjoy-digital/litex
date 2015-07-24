import os
from fractions import Fraction
from math import ceil

from migen.fhdl.std import *
from mibuild.generic_platform import ConstraintError

from misoclib.mem.sdram.module import MT46V32M16
from misoclib.mem.sdram.phy import s6ddrphy
from misoclib.mem.sdram.core.lasmicon import LASMIconSettings
from misoclib.mem.flash import norflash16
from misoclib.video import framebuffer
from misoclib.soc import mem_decoder
from misoclib.soc.sdram import SDRAMSoC
from misoclib.com import gpio
from misoclib.com.liteeth.phy import LiteEthPHY
from misoclib.com.liteeth.core.mac import LiteEthMAC


class _MXCRG(Module):
    def __init__(self, pads, outfreq1x):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sdram_half = ClockDomain()
        self.clock_domains.cd_sdram_full_wr = ClockDomain()
        self.clock_domains.cd_sdram_full_rd = ClockDomain()
        self.clock_domains.cd_base50 = ClockDomain(reset_less=True)

        self.clk4x_wr_strb = Signal()
        self.clk4x_rd_strb = Signal()

        ###

        infreq = 50*1000000
        ratio = Fraction(outfreq1x)/Fraction(infreq)
        in_period = float(Fraction(1000000000)/Fraction(infreq))

        self.specials += Instance("mxcrg",
                                  Instance.Parameter("in_period", in_period),
                                  Instance.Parameter("f_mult", ratio.numerator),
                                  Instance.Parameter("f_div", ratio.denominator),
                                  Instance.Input("clk50_pad", pads.clk50),
                                  Instance.Input("trigger_reset", pads.trigger_reset),

                                  Instance.Output("sys_clk", self.cd_sys.clk),
                                  Instance.Output("sys_rst", self.cd_sys.rst),
                                  Instance.Output("clk2x_270", self.cd_sdram_half.clk),
                                  Instance.Output("clk4x_wr", self.cd_sdram_full_wr.clk),
                                  Instance.Output("clk4x_rd", self.cd_sdram_full_rd.clk),
                                  Instance.Output("base50_clk", self.cd_base50.clk),

                                  Instance.Output("clk4x_wr_strb", self.clk4x_wr_strb),
                                  Instance.Output("clk4x_rd_strb", self.clk4x_rd_strb),
                                  Instance.Output("norflash_rst_n", pads.norflash_rst_n),
                                  Instance.Output("ddr_clk_pad_p", pads.ddr_clk_p),
                                  Instance.Output("ddr_clk_pad_n", pads.ddr_clk_n))


class _MXClockPads:
    def __init__(self, platform):
        self.clk50 = platform.request("clk50")
        self.trigger_reset = 0
        try:
            self.trigger_reset = platform.request("user_btn", 1)
        except ConstraintError:
            pass
        self.norflash_rst_n = platform.request("norflash_rst_n")
        ddram_clock = platform.request("ddram_clock")
        self.ddr_clk_p = ddram_clock.p
        self.ddr_clk_n = ddram_clock.n


class BaseSoC(SDRAMSoC):
    default_platform = "mixxeo"  # also supports m1

    def __init__(self, platform, sdram_controller_settings=LASMIconSettings(), **kwargs):
        SDRAMSoC.__init__(self, platform,
                          clk_freq=(83 + Fraction(1, 3))*1000000,
                          cpu_reset_address=0x00180000,
                          sdram_controller_settings=sdram_controller_settings,
                          **kwargs)

        self.submodules.crg = _MXCRG(_MXClockPads(platform), self.clk_freq)

        if not self.integrated_main_ram_size:
            self.submodules.ddrphy = s6ddrphy.S6DDRPHY(platform.request("ddram"),
                                                       MT46V32M16(self.clk_freq),
                                                       rd_bitslip=0,
                                                       wr_bitslip=3,
                                                       dqs_ddr_alignment="C1")
            self.register_sdram_phy(self.ddrphy)
            self.comb += [
                self.ddrphy.clk4x_wr_strb.eq(self.crg.clk4x_wr_strb),
                self.ddrphy.clk4x_rd_strb.eq(self.crg.clk4x_rd_strb)
            ]

        if not self.integrated_rom_size:
            clk_period_ns = 1000000000/self.clk_freq
            self.submodules.norflash = norflash16.NorFlash16(platform.request("norflash"),
                ceil(110/clk_period_ns), ceil(50/clk_period_ns))
            self.flash_boot_address = 0x001a0000
            self.register_rom(self.norflash.bus)

        platform.add_platform_command("""
INST "mxcrg/wr_bufpll" LOC = "BUFPLL_X0Y2";
INST "mxcrg/rd_bufpll" LOC = "BUFPLL_X0Y3";
""")
        platform.add_source(os.path.join("misoclib", "mxcrg.v"))


class MiniSoC(BaseSoC):
    csr_map = {
        "ethphy": 16,
        "ethmac": 17,
    }
    csr_map.update(BaseSoC.csr_map)

    interrupt_map = {
        "ethmac": 2,
    }
    interrupt_map.update(BaseSoC.interrupt_map)

    mem_map = {
        "ethmac": 0x30000000,  # (shadow @0xb0000000)
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, platform, **kwargs):
        BaseSoC.__init__(self, platform, **kwargs)

        if platform.name == "mixxeo":
            self.submodules.leds = gpio.GPIOOut(platform.request("user_led"))
        if platform.name == "m1":
            self.submodules.buttons = gpio.GPIOIn(Cat(platform.request("user_btn", 0),
                                                      platform.request("user_btn", 2)))
            self.submodules.leds = gpio.GPIOOut(Cat(platform.request("user_led", i) for i in range(2)))

        self.submodules.ethphy = LiteEthPHY(platform.request("eth_clocks"),
                                            platform.request("eth"))
        self.submodules.ethmac = LiteEthMAC(phy=self.ethphy, dw=32, interface="wishbone")
        self.add_wb_slave(mem_decoder(self.mem_map["ethmac"]), self.ethmac.bus)
        self.add_memory_region("ethmac", self.mem_map["ethmac"] | self.shadow_base, 0x2000)


def get_vga_dvi(platform):
    try:
        pads_vga = platform.request("vga_out")
    except ConstraintError:
        pads_vga = None
    try:
        pads_dvi = platform.request("dvi_out")
    except ConstraintError:
        pads_dvi = None
    else:
        platform.add_platform_command("""
PIN "dviout_pix_bufg.O" CLOCK_DEDICATED_ROUTE = FALSE;
""")
    return pads_vga, pads_dvi


def add_vga_tig(platform, fb):
    platform.add_platform_command("""
NET "{vga_clk}" TNM_NET = "GRPvga_clk";
NET "sys_clk" TNM_NET = "GRPsys_clk";
TIMESPEC "TSise_sucks1" = FROM "GRPvga_clk" TO "GRPsys_clk" TIG;
TIMESPEC "TSise_sucks2" = FROM "GRPsys_clk" TO "GRPvga_clk" TIG;
""", vga_clk=fb.driver.clocking.cd_pix.clk)


class FramebufferSoC(MiniSoC):
    csr_map = {
        "fb": 18,
    }
    csr_map.update(MiniSoC.csr_map)

    def __init__(self, platform, **kwargs):
        MiniSoC.__init__(self, platform, **kwargs)
        pads_vga, pads_dvi = get_vga_dvi(platform)
        self.submodules.fb = framebuffer.Framebuffer(pads_vga, pads_dvi,
                                                     self.sdram.crossbar.get_master())
        add_vga_tig(platform, self.fb)

default_subtarget = FramebufferSoC
