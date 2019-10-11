# litex/soc/cores/cpu/blackparrot/core.py
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
#    "linux":    "freechips.rocketchip.system.LitexLinuxConfig",
#    "full":     "freechips.rocketchip.system.LitexFullConfig",
}

GCC_FLAGS = {
    "standard": "-march=rv64ia   -mabi=lp64 -O0 ",
#    "linux":    "-march=rv64imac   -mabi=lp64 ",
#    "full":     "-march=rv64imafdc -mabi=lp64 ",
}

class BlackParrotRV64(Module):
    name                 = "blackparrot"
    data_width           = 64
    endianness           = "little"
    gcc_triple           = ("riscv64-unknown-elf")
    linker_output_format = "elf64-littleriscv"
 #   io_regions           = {0x10000000: 0x70000000} # origin, length
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
        print("SC: Check how to get cpu_reset_addr properly!!!!!!!!")
        #assert cpu_reset_addr == 0x10000000, "cpu_reset_addr hardcoded in Chisel elaboration!"

        self.platform = platform
        self.variant = variant
        self.reset = Signal()
        self.interrupt = Signal(4)#TODO: how interrupts work?
#        print(self.interrupt)
# old       self.wbone = wbn = wishbone.Interface(data_width=64, adr_width=40)
        self.wbone = wbn = wishbone.Interface(data_width=64, adr_width=37)

        self.interrupts = {}#TODO: Idk why this is necessary. Without this, soc_core.py raises error with no object attirubute "interrupts" 

        self.buses     = [wbn]
        # # #
        # connect BP adaptor to Wishbone
        self.cpu_params = dict(
            # clock, reset
            i_clk_i = ClockSignal(),
            i_reset_i = ResetSignal() | self.reset,
            # irq
            i_interrupts = self.interrupt,
            i_wbm_dat_i = wbn.dat_r,
            o_wbm_dat_o = wbn.dat_w,
            i_wbm_ack_i = wbn.ack,
           # i_wbm_err_i = wbn.err,
           # i_wbm_rty_i = wbn.try,
            o_wbm_adr_o = wbn.adr,
            o_wbm_stb_o = wbn.stb,
            o_wbm_cyc_o = wbn.cyc,
            o_wbm_sel_o = wbn.sel,
            o_wbm_we_o = wbn.we,
            o_wbm_cti_o = wbn.cti,
            o_wbm_bte_o = wbn.bte,
        )

#        self.submodules += mem_a2w,  mmio_a2w #need to change most probably!
           # add verilog sources
        self.add_sources(platform, variant)

    def set_reset_address(self, reset_address):#note sure if reset address needs to be changed for BB
        assert not hasattr(self, "reset_address")
        self.reset_address = reset_address
        print(hex(reset_address))
        #assert reset_address == 0x10000000, "cpu_reset_addr hardcoded in during elaboration!"


    @staticmethod
    def add_sources(platform, variant="standard"):
        #Read from a file and use add_source function
      #  vdir = os.path.join(
        #os.path.abspath(os.path.dirname(__file__)),"pre-alpha-release", "verilog",variant)
      #  incdir = os.path.join(
        #os.path.abspath(os.path.dirname(__file__)),"pre-alpha-release", "verilog",variant)
        print("Adding the sources")
        #vdir = os.path.join(
        #os.path.abspath(os.path.dirname(__file__)),"verilog")
        #platform.add_source_dir(vdir)
        filename= os.path.join(os.path.abspath(os.path.dirname(__file__)),"flist_litex.verilator")
        print(filename)
#        platform.add_source('/home/scanakci/Research_sado/litex/litex/litex/soc/cores/cpu/blackparrot/pre-alpha-release/bp_fpga/ExampleBlackParrotSystem.v')
        with open(filename) as openfileobject:
            for line in openfileobject:
                temp = line
        #        print(line)
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


