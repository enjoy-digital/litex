#
# This file is part of LiteX.
# SPDX-License-Identifier: BSD-2-Clause

"""Run BIOS mutation handlers and the real DMA admission lifecycle on the host."""
import unittest
from test.software import test_usnative as firmware
from test.software.test_usnative_retry import function

@unittest.skipUnless(firmware.CC, "Host C compiler required")
class TestSDRAMDMAInvalidation(unittest.TestCase):
    compile_run=firmware.TestUSNativeFirmware.compile_run

    def test_phy_mr_mutations_require_complete_reinitialization(self):
        source=firmware.ROOT/'litex/soc/software/liblitedram/sdram.c'
        commands=firmware.ROOT/'litex/soc/software/bios/cmds/cmd_litedram.c'
        names=['sdram_force_rdphase','sdram_force_wrphase','sdram_rst_cmd_delay',
               'sdram_force_cmd_delay','sdram_cal','sdram_rst_dat_delay',
               'sdram_force_dat_delay','sdram_rst_bitslip','sdram_force_bitslip','sdram_mr_write']
        bodies=''.join(function(source,sig) for sig in [
            'void sdram_invalidate_dma(', 'void sdram_software_control_on(',
            'void sdram_software_control_off('])
        handlers=''.join(function(commands,'static void '+name+'_handler(') for name in names)
        full=function(source,'int sdram_init(')
        stub=r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#define CONFIG_SDRAM_CUSTOM_INIT
#define DFII_CONTROL_SOFTWARE 14
#define DFII_CONTROL_HARDWARE 1
#define MAIN_RAM_BASE 0x40000000ul
#define MAIN_RAM_BASE_VA MAIN_RAM_BASE
#define MEMTEST_DATA_SIZE 64
static unsigned admission=1,owner=1,changed,mem_ok=1,memtests;
#ifdef CONFIG_SDRAM_DMA_SOFTWARE_ADMISSION
static void dma_bench_software_ready_write(unsigned v) {admission=v;}
#endif
static unsigned sdram_dfii_control_read(void) {return owner;}
static void sdram_dfii_control_write(unsigned v) {
#ifdef CONFIG_SDRAM_DMA_SOFTWARE_ADMISSION
 assert(!admission);
#endif
 owner=v;
}
static void mutation(void) {
#ifdef CONFIG_SDRAM_DMA_SOFTWARE_ADMISSION
 assert(!admission);
#endif
 ++changed;
}
static void ddrphy_rdphase_write(unsigned v) {(void)v;mutation();}
static void ddrphy_wrphase_write(unsigned v) {(void)v;mutation();}
static void sdram_write_leveling_rst_cmd_delay(unsigned v) {(void)v;mutation();}
static void sdram_write_leveling_force_cmd_delay(unsigned a,unsigned b) {(void)a;(void)b;mutation();}
static void sdram_leveling(void) {mutation();}
static void sdram_write_leveling_rst_dat_delay(unsigned a,unsigned b) {(void)a;(void)b;mutation();}
static void sdram_write_leveling_force_dat_delay(unsigned a,unsigned b,unsigned c) {(void)a;(void)b;(void)c;mutation();}
static void sdram_write_leveling_rst_bitslip(unsigned a,unsigned b) {(void)a;(void)b;mutation();}
static void sdram_write_leveling_force_bitslip(unsigned a,unsigned b,unsigned c) {(void)a;(void)b;(void)c;mutation();}
static void sdram_mode_register_write(unsigned a,unsigned b) {(void)a;(void)b;mutation();}
static int memtest(unsigned *p,unsigned size) {
 (void)p;(void)size;assert(owner==1);
#ifdef CONFIG_SDRAM_DMA_SOFTWARE_ADMISSION
 assert(!admission);
#endif
 ++memtests;return mem_ok;
}
static void memspeed(unsigned *p,unsigned size,int w,int rnd) {(void)p;(void)size;(void)w;(void)rnd;}
'''
        training='static int sdram_custom_init(void) {sdram_software_control_on();return 1;}\n'
        main='int main(void) {\n void (*handlers[])(int,char** )={'+','.join(x+'_handler' for x in names)+'};\n'+r'''
 char *valid[]={"1","2"},*invalid[]={"invalid"};
 assert(sdram_init() && admission);
 sdram_software_control_on();sdram_software_control_off();
#ifdef CONFIG_SDRAM_DMA_SOFTWARE_ADMISSION
 assert(!admission);
#endif
 assert(sdram_init() && admission);
 for(unsigned i=0;i<sizeof(handlers)/sizeof(handlers[0]);++i) {
  unsigned before=changed;handlers[i](2,valid);
  assert(changed==before+1 && owner==1);
#ifdef CONFIG_SDRAM_DMA_SOFTWARE_ADMISSION
  assert(!admission);sdram_software_control_off();assert(!admission);
#endif
  assert(sdram_init() && admission);
 }
 unsigned before=changed;
 sdram_force_rdphase_handler(1,invalid);sdram_force_wrphase_handler(0,invalid);
 assert(admission && changed==before);
 sdram_invalidate_dma();mem_ok=0;assert(!sdram_init());
#ifdef CONFIG_SDRAM_DMA_SOFTWARE_ADMISSION
 assert(!admission);
#endif
 mem_ok=1;assert(sdram_init() && admission);
 return 0;
}
'''
        for dma in [False,True]:
            with self.subTest(dma=dma):
                self.compile_run(('#define CONFIG_SDRAM_DMA_SOFTWARE_ADMISSION\n' if dma else '')+
                                 stub+bodies+training+handlers+full+main)
