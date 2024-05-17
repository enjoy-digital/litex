#
# This file is part of LiteX.
#
# Copyright (c) 2022 Ilia Sergachev <ilia.sergachev@protonmail.ch>
# SPDX-License-Identifier: BSD-2-Clause

import os

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

    def set_preset(self, preset):
        preset = os.path.abspath(preset)
        self.ps_tcl.append(f"source {preset}")
        self.ps_tcl.append("set psu_cfg [apply_preset IPINST]")
        self.ps_tcl.append("set_property -dict $psu_cfg [get_ips {}]".format(self.ps_name))

    def add_axi_gp_master(self, n=0, data_width=32):
        assert n < 3 and self.axi_gp_masters[n] is None
        assert data_width in [32, 64, 128]
        axi_gpn = axi.AXIInterface(data_width=data_width, address_width=32, id_width=16)
        xpd     = {0 : "fpd", 1 : "fpd", 2 : "lpd"}[n]
        self.config[f'PSU__USE__M_AXI_GP{n}']      = 1
        self.config[f'PSU__MAXIGP{n}__DATA_WIDTH'] = data_width
        self.axi_gp_masters.append(axi_gpn)
        self.cpu_params.update({
            # AXI GPx clk.
            f"i_maxihpm0_{xpd}_aclk" : ClockSignal("ps"),

            # AXI GPx aw.
            f"o_maxigp{n}_awid"      : axi_gpn.aw.id,
            f"o_maxigp{n}_awaddr"    : axi_gpn.aw.addr,
            f"o_maxigp{n}_awlen"     : axi_gpn.aw.len,
            f"o_maxigp{n}_awsize"    : axi_gpn.aw.size,
            f"o_maxigp{n}_awburst"   : axi_gpn.aw.burst,
            f"o_maxigp{n}_awlock"    : axi_gpn.aw.lock,
            f"o_maxigp{n}_awcache"   : axi_gpn.aw.cache,
            f"o_maxigp{n}_awprot"    : axi_gpn.aw.prot,
            f"o_maxigp{n}_awvalid"   : axi_gpn.aw.valid,
            f"o_maxigp{n}_awuser"    : axi_gpn.aw.user,
            f"i_maxigp{n}_awready"   : axi_gpn.aw.ready,
            f"o_maxigp{n}_awqos"     : axi_gpn.aw.qos,

            # AXI GPx w.
            f"o_maxigp{n}_wdata"     : axi_gpn.w.data,
            f"o_maxigp{n}_wstrb"     : axi_gpn.w.strb,
            f"o_maxigp{n}_wlast"     : axi_gpn.w.last,
            f"o_maxigp{n}_wvalid"    : axi_gpn.w.valid,
            f"i_maxigp{n}_wready"    : axi_gpn.w.ready,

            # AXI GPx b.
            f"i_maxigp{n}_bid"       : axi_gpn.b.id,
            f"i_maxigp{n}_bresp"     : axi_gpn.b.resp,
            f"i_maxigp{n}_bvalid"    : axi_gpn.b.valid,
            f"o_maxigp{n}_bready"    : axi_gpn.b.ready,

            # AXI GPx ar.
            f"o_maxigp{n}_arid"      : axi_gpn.ar.id,
            f"o_maxigp{n}_araddr"    : axi_gpn.ar.addr,
            f"o_maxigp{n}_arlen"     : axi_gpn.ar.len,
            f"o_maxigp{n}_arsize"    : axi_gpn.ar.size,
            f"o_maxigp{n}_arburst"   : axi_gpn.ar.burst,
            f"o_maxigp{n}_arlock"    : axi_gpn.ar.lock,
            f"o_maxigp{n}_arcache"   : axi_gpn.ar.cache,
            f"o_maxigp{n}_arprot"    : axi_gpn.ar.prot,
            f"o_maxigp{n}_arvalid"   : axi_gpn.ar.valid,
            f"o_maxigp{n}_aruser"    : axi_gpn.ar.user,
            f"i_maxigp{n}_arready"   : axi_gpn.ar.ready,
            f"o_maxigp{n}_arqos"     : axi_gpn.ar.qos,

            # AXI GPx r.
            f"i_maxigp{n}_rid"       : axi_gpn.r.id,
            f"i_maxigp{n}_rdata"     : axi_gpn.r.data,
            f"i_maxigp{n}_rresp"     : axi_gpn.r.resp,
            f"i_maxigp{n}_rlast"     : axi_gpn.r.last,
            f"i_maxigp{n}_rvalid"    : axi_gpn.r.valid,
            f"o_maxigp{n}_rready"    : axi_gpn.r.ready,
        })

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
