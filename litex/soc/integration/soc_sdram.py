# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2019 Gabriel L. Somlo <somlo@cmu.edu>
# License: BSD

from math import log2
import inspect

from migen import *
from migen.genlib.record import *

from litex.soc.interconnect import wishbone
from litex.soc.integration.soc_core import *

from litedram.frontend.wishbone import *
from litedram.frontend.axi import *
from litedram.core import LiteDRAMCore

__all__ = ["SoCSDRAM", "soc_sdram_args", "soc_sdram_argdict"]

# SoCSDRAM -----------------------------------------------------------------------------------------

class SoCSDRAM(SoCCore):
    csr_map = {
        "sdram":    8,
        "l2_cache": 9,
    }
    csr_map.update(SoCCore.csr_map)

    def __init__(self, platform, clk_freq, l2_size=8192, l2_reverse=True, min_l2_data_width=128, max_sdram_size=None, **kwargs):
        SoCCore.__init__(self, platform, clk_freq, **kwargs)
        if not self.integrated_main_ram_size:
            if self.cpu_type is not None and self.csr_data_width > 32:
                 raise NotImplementedError("BIOS supports SDRAM initialization only for csr_data_width<=32")
        self.l2_size           = l2_size
        self.l2_reverse        = l2_reverse
        self.min_l2_data_width = min_l2_data_width
        self.max_sdram_size    = max_sdram_size

        self._sdram_phy    = []
        self._wb_sdram_ifs = []
        self._wb_sdram     = wishbone.Interface()

    def add_wb_sdram_if(self, interface):
        if self.finalized:
            raise FinalizeError
        self._wb_sdram_ifs.append(interface)

    def register_sdram(self, phy, geom_settings, timing_settings, **kwargs):
        assert not self._sdram_phy
        self._sdram_phy.append(phy) # encapsulate in list to prevent CSR scanning

        # LiteDRAM core ----------------------------------------------------------------------------
        self.submodules.sdram = LiteDRAMCore(
            phy             = phy,
            geom_settings   = geom_settings,
            timing_settings = timing_settings,
            clk_freq        = self.clk_freq,
            **kwargs)

        # LiteDRAM port ------------------------------------------------------------------------
        port = self.sdram.crossbar.get_port()
        port.data_width = 2**int(log2(port.data_width)) # Round to nearest power of 2

        # Main RAM size ------------------------------------------------------------------------
        main_ram_size = 2**(geom_settings.bankbits +
                            geom_settings.rowbits +
                            geom_settings.colbits)*phy.settings.databits//8
        if self.max_sdram_size is not None:
            main_ram_size = min(main_ram_size, self.max_sdram_size)

        # SoC [<--> L2 Cache] <--> LiteDRAM ----------------------------------------------------
        if self.cpu.name == "rocket":
            # Rocket has its own I/D L1 cache: connect directly to LiteDRAM, also bypassing MMIO/CSR wb bus:
            if port.data_width == self.cpu.mem_axi.data_width:
                print("# Matching AXI MEM data width ({})\n".format(port.data_width))
                # straightforward AXI link, no data_width conversion needed:
                self.submodules += LiteDRAMAXI2Native(self.cpu.mem_axi, port,
                                                      base_address=self.mem_map["main_ram"])
            else:
                print("# Converting MEM data width: ram({}) to cpu({}), via Wishbone\n".format(port.data_width, self.cpu.mem_axi.data_width))
                # FIXME: replace WB data-width converter with native AXI converter!!!
                mem_wb  = wishbone.Interface(data_width=self.cpu.mem_axi.data_width,
                                             adr_width=32-log2_int(self.cpu.mem_axi.data_width//8))
                # NOTE: AXI2Wishbone FSMs must be reset with the CPU!
                mem_a2w = ResetInserter()(AXI2Wishbone(self.cpu.mem_axi, mem_wb, base_address=0))
                self.comb += mem_a2w.reset.eq(ResetSignal() | self.cpu.reset)
                self.submodules += mem_a2w
                litedram_wb = wishbone.Interface(port.data_width)
                self.submodules += LiteDRAMWishbone2Native(litedram_wb, port,
                                                           base_address=self.mem_map["main_ram"])
                self.submodules += wishbone.Converter(mem_wb, litedram_wb)
            # Register main_ram region (so it will be added to generated/mem.h):
            self.add_memory_region("main_ram", self.mem_map["main_ram"], main_ram_size)
        elif self.with_wishbone:
            # Insert L2 cache inbetween Wishbone bus and LiteDRAM
            l2_size = max(self.l2_size, int(2*port.data_width/8)) # L2 has a minimal size, use it if lower
            l2_size = 2**int(log2(l2_size))                       # Round to nearest power of 2

            # SoC <--> L2 Cache Wishbone interface -------------------------------------------------
            wb_sdram = wishbone.Interface()
            self.add_wb_sdram_if(wb_sdram)
            self.register_mem("main_ram", self.mem_map["main_ram"], wb_sdram, main_ram_size)

            # L2 Cache -----------------------------------------------------------------------------
            l2_data_width = max(port.data_width, self.min_l2_data_width)
            l2_cache = wishbone.Cache(
                cachesize = l2_size//4,
                master    = self._wb_sdram,
                slave     = wishbone.Interface(l2_data_width),
                reverse   = self.l2_reverse)
            # XXX Vivado ->2018.2 workaround, Vivado is not able to map correctly our L2 cache.
            # Issue is reported to Xilinx, Remove this if ever fixed by Xilinx...
            from litex.build.xilinx.vivado import XilinxVivadoToolchain
            if isinstance(self.platform.toolchain, XilinxVivadoToolchain):
                from migen.fhdl.simplify import FullMemoryWE
                self.submodules.l2_cache = FullMemoryWE()(l2_cache)
            else:
                self.submodules.l2_cache = l2_cache
            self.config["L2_SIZE"] = l2_size

            # L2 Cache <--> LiteDRAM bridge --------------------------------------------------------
            self.submodules.wishbone_bridge = LiteDRAMWishbone2Native(self.l2_cache.slave, port)

    def do_finalize(self):
        if not self.integrated_main_ram_size:
            if not self._sdram_phy:
                raise FinalizeError("Need to call SoCSDRAM.register_sdram()")

            # Arbitrate wishbone interfaces to the DRAM
            if len(self._wb_sdram_ifs) != 0:
                self.submodules.wb_sdram_con = wishbone.Arbiter(self._wb_sdram_ifs, self._wb_sdram)
        SoCCore.do_finalize(self)


# SoCSDRAM arguments --------------------------------------------------------------------------------

def soc_sdram_args(parser):
    soc_core_args(parser)
    # L2 Cache
    parser.add_argument("--l2-size", default=8192,
                        help="L2 cache size (default=8192)")
    parser.add_argument("--min-l2-datawidth", default=128,
                        help="Minimum L2 cache datawidth (default=128)")

    # SDRAM
    parser.add_argument("--max-sdram-size", default=0x40000000,
                        help="Maximum SDRAM size mapped to the SoC (default=1GB))")

def soc_sdram_argdict(args):
    r = soc_core_argdict(args)
    for a in inspect.getargspec(SoCSDRAM.__init__).args:
        if a not in ["self", "platform", "clk_freq"]:
            arg = getattr(args, a, None)
            if arg is not None:
                r[a] = arg
    return r
