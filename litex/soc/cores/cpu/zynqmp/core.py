#
# This file is part of LiteX.
#
# Copyright (c) 2022 Ilia Sergachev <ilia.sergachev@protonmail.ch>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.soc.cores.cpu import CPU
from litex.soc.interconnect import axi


# Zynq MP ------------------------------------------------------------------------------------------

class ZynqMP(CPU):
    variants             = ["standard"]
    category             = "hardcore"
    family               = "aarch64"
    name                 = "zynqmp"
    human_name           = "Zynq Ultrascale+ MPSoC"
    data_width           = 64
    endianness           = "little"
    reset_address        = 0xc000_0000
    gcc_triple           = "aarch64-none-elf"
    gcc_flags            = ""
    linker_output_format = "elf64-littleaarch64"
    nop                  = "nop"
    io_regions           = {  # Origin, Length.
        0x8000_0000: 0x00_4000_0000,
        0xe000_0000: 0xff_2000_0000  # TODO: there are more details here
    }
    csr_decode           = True # AXI address is decoded in AXI2Wishbone, offset needs to be added in Software.

    @property
    def mem_map(self):
        return {
            "sram": 0x0000_0000,  # DDR low in fact
            "rom":  0xc000_0000,  # Quad SPI memory
        }

    def __init__(self, platform, variant, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.platform = platform
        self.reset          = Signal()
        self.periph_buses   = []          # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses   = []          # Memory buses (Connected directly to LiteDRAM).
        self.axi_gp_masters = [None] * 3  # General Purpose AXI Masters.

        self.cd_ps = ClockDomain()

        self.ps_name = "ps"
        self.ps_tcl = []
        self.config = {'PSU__FPGA_PL0_ENABLE': 1}  # enable pl_clk0
        rst_n = Signal()
        self.cpu_params = dict(
            o_pl_clk0=ClockSignal("ps"),
            o_pl_resetn0=rst_n
        )
        self.comb += ResetSignal("ps").eq(~rst_n)
        self.ps_tcl.append(f"set ps [create_ip -vendor xilinx.com -name zynq_ultra_ps_e -module_name {self.ps_name}]")

    def add_axi_gp_master(self, n=0, data_width=32):
        assert n < 3 and self.axi_gp_masters[n] is None
        assert data_width in [32, 64, 128]
        axi_gpn = axi.AXIInterface(data_width=data_width, address_width=32, id_width=16)
        self.config[f'PSU__USE__M_AXI_GP{n}'] = 1
        self.config[f'PSU__MAXIGP{n}__DATA_WIDTH'] = data_width
        self.axi_gp_masters.append(axi_gpn)
        xpd = {0 : "fpd", 1 : "fpd", 2 : "lpd"}[n]
        self.cpu_params[f"i_maxihpm0_{xpd}_aclk"] = ClockSignal("ps")
        layout = axi_gpn.layout_flat()
        dir_map = {DIR_M_TO_S: 'o', DIR_S_TO_M: 'i'}
        for group, signal, direction in layout:
            sig_name = group + signal
            if sig_name in ['bfirst', 'blast', 'rfirst', 'arfirst', 'arlast', 'awfirst', 'awlast', 'wfirst', 'wid']:
                continue
            direction = dir_map[direction]
            self.cpu_params[f'{direction}_maxigp{n}_{group}{signal}'] = getattr(getattr(axi_gpn, group), signal)

        return axi_gpn

    def do_finalize(self):
        if len(self.ps_tcl):
            self.ps_tcl.append("set_property -dict [list \\")
            for config, value in self.config.items():
                self.ps_tcl.append("CONFIG.{} {} \\".format(config, '{{' + str(value) + '}}'))
            self.ps_tcl.append(f"] [get_ips {self.ps_name}]")

            self.ps_tcl += [
                f"generate_target all [get_ips {self.ps_name}]",
                f"synth_ip [get_ips {self.ps_name}]"
            ]
            self.platform.toolchain.pre_synthesis_commands += self.ps_tcl
        self.specials += Instance(self.ps_name, **self.cpu_params)
