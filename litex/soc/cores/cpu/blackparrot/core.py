# BlackParrot Chip core support for the LiteX SoC.
#
# Authors: Sadullah Canakci & Cansu Demirkiran  <{scanakci,cansu}@bu.edu>
# Copyright (c) 2019, Boston University
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#
#     * Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os

from migen import *

from litex.soc.interconnect import axi
from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU

CPU_VARIANTS = {
    "standard": "freechips.rocketchip.system.LitexConfig",
}

GCC_FLAGS = {
    "standard": "-march=rv64ia   -mabi=lp64 -O0 ",
}

class BlackParrotRV64(CPU):
    name                 = "blackparrot"
    data_width           = 64
    endianness           = "little"
    gcc_triple           = ("riscv64-unknown-elf", "riscv64-linux")
    linker_output_format = "elf64-littleriscv"
    io_regions           = {0x30000000: 0x20000000} # origin, length

    @property
    def mem_map(self):
        return {
            "ethmac"   : 0x30000000,
            "csr"      : 0x40000000,
            "rom"      : 0x50000000,
            "sram"     : 0x51000000,
            "main_ram" : 0x80000000,
        }

    @property
    def gcc_flags(self):
        flags =  "-mno-save-restore "
        flags += GCC_FLAGS[self.variant]
        flags += "-D__blackparrot__ "
        return flags

    def __init__(self, platform, variant="standard"):
        assert variant in CPU_VARIANTS, "Unsupported variant %s" % variant

        self.platform  = platform
        self.variant   = variant
        self.reset     = Signal()
        self.interrupt = Signal(4)
        self.idbus     = idbus = wishbone.Interface(data_width=64, adr_width=37)
        self.buses     = [idbus]

        # # #

        self.cpu_params = dict(
            # clock, reset
            i_clk_i      = ClockSignal(),
            i_reset_i    = ResetSignal() | self.reset,

            # irq
            i_interrupts = self.interrupt,

            # wishbone
            i_wbm_dat_i  = idbus.dat_r,
            o_wbm_dat_o  = idbus.dat_w,
            i_wbm_ack_i  = idbus.ack,
            i_wbm_err_i  = 0,
            i_wbm_rty_i  = 0,
            o_wbm_adr_o  = idbus.adr,
            o_wbm_stb_o  = idbus.stb,
            o_wbm_cyc_o  = idbus.cyc,
            o_wbm_sel_o  = idbus.sel,
            o_wbm_we_o   = idbus.we,
            o_wbm_cti_o  = idbus.cti,
            o_wbm_bte_o  = idbus.bte,
        )

        # add verilog sources
        self.add_sources(platform, variant)

    def set_reset_address(self, reset_address):
        assert not hasattr(self, "reset_address")
        self.reset_address = reset_address
        assert reset_address == 0x00000000, "cpu_reset_addr hardcoded to 0x00000000!"

    @staticmethod
    def add_sources(platform, variant="standard"):
        filename = os.path.join(os.path.abspath(os.path.dirname(__file__)), "flist_litex.verilator")
        with open(filename) as openfileobject:
            for line in openfileobject:
                temp = line
                if (temp[0] == '/' and temp[1] == '/'):
                    continue
                elif ("+incdir+" in temp) :
                    s1 = line.find('$')
                    s2 = line.find('/')
                    dir_ = line[s1:s2]
                    a = os.popen('echo '+ str(dir_))
                    dir_start = a.read()
                    vdir = dir_start[:-1] + line[s2:-1]
                    print("INCDIR" + vdir)
                    platform.add_verilog_include_path(vdir)  #this line might be changed
                elif (temp[0]=='$') :
                    s2 = line.find('/')
                    dir_ = line[0:s2]
                    a = os.popen('echo '+ str(dir_))
                    dir_start = a.read()
                    vdir = dir_start[:-1]+ line[s2:-1]
                    print(vdir)
                    platform.add_source(vdir) #this line might be changed
                elif (temp[0] == '/'):
                    assert("No support for absolute path for now")

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("ExampleBlackParrotSystem", **self.cpu_params)


