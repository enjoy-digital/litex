from litex.gen import *
from litex.gen.genlib.record import *

from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import AutoCSR
from litex.soc.integration.soc_core import *

from litedram.frontend import crossbar
from litedram.frontend.bridge import LiteDRAMWishboneBridge
from litedram import dfii, core


__all__ = ["SoCSDRAM", "soc_sdram_args", "soc_sdram_argdict"]


class ControllerInjector(Module, AutoCSR):
    def __init__(self, phy, geom_settings, timing_settings, controller_settings):
        self.submodules.dfii = dfii.DFIInjector(geom_settings.addressbits, geom_settings.bankbits,
                phy.settings.dfi_databits, phy.settings.nphases)
        self.comb += self.dfii.master.connect(phy.dfi)

        self.submodules.controller = controller = core.LiteDRAMController(phy.settings,
                                                                          geom_settings,
                                                                          timing_settings,
                                                                          controller_settings)
        self.comb += controller.dfi.connect(self.dfii.slave)

        self.submodules.crossbar = crossbar.LiteDRAMCrossbar(controller.lasmic, controller.nrowbits)


class SoCSDRAM(SoCCore):
    csr_map = {
        "sdram":           8,
        "l2_cache":        9
    }
    csr_map.update(SoCCore.csr_map)

    def __init__(self, platform, clk_freq, l2_size=8192, **kwargs):
        SoCCore.__init__(self, platform, clk_freq, **kwargs)
        self.l2_size = l2_size

        self._sdram_phy = []
        self._wb_sdram_ifs = []
        self._wb_sdram = wishbone.Interface()

    def add_wb_sdram_if(self, interface):
        if self.finalized:
            raise FinalizeError
        self._wb_sdram_ifs.append(interface)

    def register_sdram(self, phy, geom_settings, timing_settings, controller_settings=None):
        assert not self._sdram_phy
        self._sdram_phy.append(phy)  # encapsulate in list to prevent CSR scanning

        self.submodules.sdram = ControllerInjector(phy,
                                                   geom_settings,
                                                   timing_settings,
                                                   controller_settings)

        dfi_databits_divisor = 1 if phy.settings.memtype == "SDR" else 2
        sdram_width = phy.settings.dfi_databits//dfi_databits_divisor
        main_ram_size = 2**(geom_settings.bankbits +
                            geom_settings.rowbits +
                            geom_settings.colbits)*sdram_width//8
        # XXX: Limit main_ram_size to 256MB, we should modify mem_map to allow larger memories.
        main_ram_size = min(main_ram_size, 256*1024*1024)
        self.add_constant("L2_SIZE", self.l2_size)

        # add a Wishbone interface to the DRAM
        wb_sdram = wishbone.Interface()
        self.add_wb_sdram_if(wb_sdram)
        self.register_mem("main_ram", self.mem_map["main_ram"], wb_sdram, main_ram_size)

        if self.l2_size:
            port = self.sdram.crossbar.get_port()
            l2_cache = wishbone.Cache(self.l2_size//4, self._wb_sdram, wishbone.Interface(port.dw))
            # XXX Vivado ->2015.1 workaround, Vivado is not able to map correctly our L2 cache.
            # Issue is reported to Xilinx and should be fixed in next releases (2015.2?).
            # Remove this workaround when fixed by Xilinx.
            from litex.build.xilinx.vivado import XilinxVivadoToolchain
            if isinstance(self.platform.toolchain, XilinxVivadoToolchain):
                from litex.gen.fhdl.simplify import FullMemoryWE
                self.submodules.l2_cache = FullMemoryWE()(l2_cache)
            else:
                self.submodules.l2_cache = l2_cache
            self.submodules.wishbone_bridge = LiteDRAMWishboneBridge(self.l2_cache.slave, port)

    def do_finalize(self):
        if not self.integrated_main_ram_size:
            if not self._sdram_phy:
                raise FinalizeError("Need to call SDRAMSoC.register_sdram()")

            # arbitrate wishbone interfaces to the DRAM
            self.submodules.wb_sdram_con = wishbone.Arbiter(self._wb_sdram_ifs,
                                                            self._wb_sdram)
        SoCCore.do_finalize(self)


soc_sdram_args = soc_core_args
soc_sdram_argdict = soc_core_argdict
