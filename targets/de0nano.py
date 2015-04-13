from migen.fhdl.std import *

from misoclib.mem.sdram.module import IS42S16160
from misoclib.mem.sdram.phy import gensdrphy
from misoclib.mem.sdram.core.lasmicon import LASMIconSettings
from misoclib.soc.sdram import SDRAMSoC


class _PLL(Module):
    def __init__(self, period_in, name, phase_shift, operation_mode):
        self.clk_in = Signal()
        self.clk_out = Signal()

        self.specials += Instance("ALTPLL",
                                  p_bandwidth_type = "AUTO",
                                  p_clk0_divide_by = 1,
                                  p_clk0_duty_cycle = 50,
                                  p_clk0_multiply_by = 2,
                                  p_clk0_phase_shift = "{}".format(str(phase_shift)),
                                  p_compensate_clock = "CLK0",
                                  p_inclk0_input_frequency = int(period_in*1000),
                                  p_intended_device_family = "Cyclone IV E",
                                  p_lpm_hint = "CBX_MODULE_PREFIX={}_pll".format(name),
                                  p_lpm_type = "altpll",
                                  p_operation_mode = operation_mode,
                                  i_inclk=self.clk_in,
                                  o_clk=self.clk_out,
                                  i_areset=0,
                                  i_clkena=0x3f,
                                  i_clkswitch=0,
                                  i_configupdate=0,
                                  i_extclkena=0xf,
                                  i_fbin=1,
                                  i_pfdena=1,
                                  i_phasecounterselect=0xf,
                                  i_phasestep=1,
                                  i_phaseupdown=1,
                                  i_pllena=1,
                                  i_scanaclr=0,
                                  i_scanclk=0,
                                  i_scanclkena=1,
                                  i_scandata=0,
                                  i_scanread=0,
                                  i_scanwrite=0
        )


class _CRG(Module):
    def __init__(self, platform):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys_ps = ClockDomain()
        self.clock_domains.cd_por = ClockDomain(reset_less=True)

        clk50 = platform.request("clk50")

        sys_pll = _PLL(20, "sys", 0, "NORMAL")
        self.submodules += sys_pll
        self.comb += [
            sys_pll.clk_in.eq(clk50),
            self.cd_sys.clk.eq(sys_pll.clk_out)
        ]

        sdram_pll = _PLL(20, "sdram", -3000, "ZERO_DELAY_BUFFER")
        self.submodules += sdram_pll
        self.comb += [
            sdram_pll.clk_in.eq(clk50),
            self.cd_sys_ps.clk.eq(sdram_pll.clk_out)
        ]

        # Power on Reset (vendor agnostic)
        rst_n = Signal()
        self.sync.por += rst_n.eq(1)
        self.comb += [
            self.cd_por.clk.eq(self.cd_sys.clk),
            self.cd_sys.rst.eq(~rst_n),
            self.cd_sys_ps.rst.eq(~rst_n)
        ]

        self.comb += platform.request("sdram_clock").eq(self.cd_sys_ps.clk)


class BaseSoC(SDRAMSoC):
    default_platform = "de0nano"

    def __init__(self, platform, sdram_controller_settings=LASMIconSettings(), **kwargs):
        SDRAMSoC.__init__(self, platform,
                          clk_freq=100*1000000,
                          integrated_rom_size=0x8000,
                          sdram_controller_settings=sdram_controller_settings,
                          **kwargs)

        self.submodules.crg = _CRG(platform)

        if not self.integrated_main_ram_size:
            self.submodules.sdrphy = gensdrphy.GENSDRPHY(platform.request("sdram"),
                                                         IS42S16160(self.clk_freq))
            self.register_sdram_phy(self.sdrphy)

default_subtarget = BaseSoC
