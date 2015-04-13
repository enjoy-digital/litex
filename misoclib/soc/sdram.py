from migen.fhdl.std import *
from migen.bus import wishbone
from migen.genlib.record import *

from misoclib.mem.sdram.core import SDRAMCore
from misoclib.mem.sdram.core.lasmicon import LASMIconSettings
from misoclib.mem.sdram.core.minicon import MiniconSettings
from misoclib.mem.sdram.frontend import memtest, wishbone2lasmi
from misoclib.soc import SoC

class SDRAMSoC(SoC):
    csr_map = {
        "sdram":                8,
        "wishbone2lasmi":        9,
        "memtest_w":            10,
        "memtest_r":            11
    }
    csr_map.update(SoC.csr_map)

    def __init__(self, platform, clk_freq, sdram_controller_settings,
            **kwargs):
        SoC.__init__(self, platform, clk_freq, **kwargs)
        if isinstance(sdram_controller_settings, str):
            self.sdram_controller_settings = eval(sdram_controller_settings)
        else:
            self.sdram_controller_settings = sdram_controller_settings
        self._sdram_phy_registered = False

    def register_sdram_phy(self, phy):
        if self._sdram_phy_registered:
            raise FinalizeError
        self._sdram_phy_registered = True
        if isinstance(self.sdram_controller_settings, MiniconSettings) and phy.settings.memtype != "SDR":
            raise NotImplementedError("Minicon only supports SDR memtype for now (" + phy.settings.memtype + ")")

        # Core
        self.submodules.sdram = SDRAMCore(phy, phy.module.geom_settings, phy.module.timing_settings, self.sdram_controller_settings)

        dfi_databits_divisor = 1 if phy.settings.memtype == "SDR" else 2
        sdram_width = phy.settings.dfi_databits//dfi_databits_divisor
        main_ram_size = 2**(phy.module.geom_settings.bankbits+
                            phy.module.geom_settings.rowbits+
                            phy.module.geom_settings.colbits)*sdram_width//8
        # XXX: Limit main_ram_size to 256MB, we should modify mem_map to allow larger memories.
        main_ram_size = min(main_ram_size, 256*1024*1024)

        # LASMICON frontend
        if isinstance(self.sdram_controller_settings, LASMIconSettings):
            if self.sdram_controller_settings.with_bandwidth:
                self.sdram.controller.multiplexer.add_bandwidth()

            if self.sdram_controller_settings.with_memtest:
                self.submodules.memtest_w = memtest.MemtestWriter(self.sdram.crossbar.get_master())
                self.submodules.memtest_r = memtest.MemtestReader(self.sdram.crossbar.get_master())

            l2_size = self.sdram_controller_settings.l2_size
            if l2_size:
                # XXX Vivado 2014.X workaround, Vivado is not able to map correctly our L2 cache.
                # Issue is reported to Xilinx and should be fixed in next releases (2015.1?).
                # Remove this workaround when fixed by Xilinx.
                from mibuild.xilinx.vivado import XilinxVivadoToolchain
                if isinstance(self.platform.toolchain, XilinxVivadoToolchain):
                    from migen.fhdl.simplify import FullMemoryWE
                    self.submodules.wishbone2lasmi = FullMemoryWE()(wishbone2lasmi.WB2LASMI(l2_size//4, self.sdram.crossbar.get_master()))
                else:
                    self.submodules.wishbone2lasmi = wishbone2lasmi.WB2LASMI(l2_size//4, self.sdram.crossbar.get_master())
                self.register_mem("main_ram", self.mem_map["main_ram"], self.wishbone2lasmi.wishbone, main_ram_size)

        # MINICON frontend
        elif isinstance(self.sdram_controller_settings, MiniconSettings):
            if sdram_width == 32:
                self.register_mem("main_ram", self.mem_map["main_ram"], self.sdram.controller.bus, main_ram_size)
            elif sdram_width < 32:
                self.submodules.downconverter = downconverter = wishbone.DownConverter(32, sdram_width)
                self.comb += Record.connect(downconverter.wishbone_o, self.sdram.controller.bus)
                self.register_mem("main_ram", self.mem_map["main_ram"], downconverter.wishbone_i, main_ram_size)
            else:
                raise NotImplementedError("Unsupported SDRAM width of {} > 32".format(sdram_width))

    def do_finalize(self):
        if not self.integrated_main_ram_size:
            if not self._sdram_phy_registered:
                raise FinalizeError("Need to call SDRAMSoC.register_sdram_phy()")
        SoC.do_finalize(self)
