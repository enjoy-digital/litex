from migen.fhdl.std import *
from migen.bus import wishbone
from migen.genlib.record import *

from misoc.mem.sdram.core import SDRAMCore
from misoc.mem.sdram.core.lasmicon import LASMIconSettings
from misoc.mem.sdram.core.minicon import MiniconSettings
from misoc.mem.sdram.frontend import memtest, wishbone2lasmi
from misoc.soc import SoC


class SDRAMSoC(SoC):
    csr_map = {
        "sdram":           8,
        "l2_cache":        9,
        "memtest_w":      10,
        "memtest_r":      11
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
        self._wb_sdram_ifs = []
        self._wb_sdram = wishbone.Interface()

    def add_wb_sdram_if(self, interface):
        if self.finalized:
            raise FinalizeError
        self._wb_sdram_ifs.append(interface)

    def register_sdram_phy(self, phy):
        if self._sdram_phy_registered:
            raise FinalizeError
        self._sdram_phy_registered = True

        # Core
        self.submodules.sdram = SDRAMCore(phy,
                                          phy.module.geom_settings,
                                          phy.module.timing_settings,
                                          self.sdram_controller_settings)

        dfi_databits_divisor = 1 if phy.settings.memtype == "SDR" else 2
        sdram_width = phy.settings.dfi_databits//dfi_databits_divisor
        main_ram_size = 2**(phy.module.geom_settings.bankbits +
                            phy.module.geom_settings.rowbits +
                            phy.module.geom_settings.colbits)*sdram_width//8
        # XXX: Limit main_ram_size to 256MB, we should modify mem_map to allow larger memories.
        main_ram_size = min(main_ram_size, 256*1024*1024)
        l2_size = self.sdram_controller_settings.l2_size
        if l2_size:
            self.add_constant("L2_SIZE", l2_size)

        # add a Wishbone interface to the DRAM
        wb_sdram = wishbone.Interface()
        self.add_wb_sdram_if(wb_sdram)
        self.register_mem("main_ram", self.mem_map["main_ram"], wb_sdram, main_ram_size)

        # LASMICON frontend
        if isinstance(self.sdram_controller_settings, LASMIconSettings):
            if self.sdram_controller_settings.with_bandwidth:
                self.sdram.controller.multiplexer.add_bandwidth()

            if self.sdram_controller_settings.with_memtest:
                self.submodules.memtest_w = memtest.MemtestWriter(self.sdram.crossbar.get_master())
                self.submodules.memtest_r = memtest.MemtestReader(self.sdram.crossbar.get_master())

            if l2_size:
                lasmim = self.sdram.crossbar.get_master()
                l2_cache = wishbone.Cache(l2_size//4, self._wb_sdram, wishbone.Interface(lasmim.dw))
                # XXX Vivado ->2015.1 workaround, Vivado is not able to map correctly our L2 cache.
                # Issue is reported to Xilinx and should be fixed in next releases (2015.2?).
                # Remove this workaround when fixed by Xilinx.
                from mibuild.xilinx.vivado import XilinxVivadoToolchain
                if isinstance(self.platform.toolchain, XilinxVivadoToolchain):
                    from migen.fhdl.simplify import FullMemoryWE
                    self.submodules.l2_cache = FullMemoryWE()(l2_cache)
                else:
                    self.submodules.l2_cache = l2_cache
                self.submodules.wishbone2lasmi = wishbone2lasmi.WB2LASMI(self.l2_cache.slave, lasmim)

        # MINICON frontend
        elif isinstance(self.sdram_controller_settings, MiniconSettings):
            if l2_size:
                l2_cache = wishbone.Cache(l2_size//4, self._wb_sdram, self.sdram.controller.bus)
                # XXX Vivado ->2015.1 workaround, Vivado is not able to map correctly our L2 cache.
                # Issue is reported to Xilinx and should be fixed in next releases (2015.2?).
                # Remove this workaround when fixed by Xilinx.
                from mibuild.xilinx.vivado import XilinxVivadoToolchain
                if isinstance(self.platform.toolchain, XilinxVivadoToolchain):
                    from migen.fhdl.simplify import FullMemoryWE
                    self.submodules.l2_cache = FullMemoryWE()(l2_cache)
                else:
                    self.submodules.l2_cache = l2_cache
            else:
                self.submodules.converter = wishbone.Converter(self._wb_sdram, self.sdram.controller.bus)

    def do_finalize(self):
        if not self.integrated_main_ram_size:
            if not self._sdram_phy_registered:
                raise FinalizeError("Need to call SDRAMSoC.register_sdram_phy()")

            # arbitrate wishbone interfaces to the DRAM
            self.submodules.wb_sdram_con = wishbone.Arbiter(self._wb_sdram_ifs,
                                                            self._wb_sdram)
        SoC.do_finalize(self)
