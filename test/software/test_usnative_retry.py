#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

"""Execute production initialization code with injected training/CSR failures."""
import unittest

from test.software import test_usnative as firmware


def function(path, signature):
    source = path.read_text()
    start = source.index(signature)
    return source[start:source.index("\n}\n", start) + 3]


@unittest.skipUnless(firmware.CC, "Host C compiler required")
class TestUSNativeRetry(unittest.TestCase):
    compile_run = firmware.TestUSNativeFirmware.compile_run

    def test_ck_failure_reasons_and_unchanged_acceptance(self):
        body = function(firmware.INCLUDE / "native_burst_calibration.h", "static unsigned nb_calibrate(")
        self.compile_run(r'''
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
static char messages[4096];
static int capture(const char *format, ...) {
 va_list args; va_start(args,format);
 int n=vsnprintf(messages+strlen(messages),sizeof(messages)-strlen(messages),format,args);
 va_end(args); return n;
}
#define printf capture
#define USNATIVE_DEBUG(...) do {} while(0)
#define USNATIVE_SNAPSHOT() do {} while(0)
struct nb_window {unsigned first,last,center,short_window;};
struct nb_result {struct nb_window ck,rx[2],dq[2];};
static unsigned scenario,boots,checks,stage;
static int nb_boot(unsigned tap) {
 (void)tap; ++boots;
 return !((scenario==1 && boots==3) || (scenario==3 && boots==18));
}
static unsigned nb_check(unsigned count,unsigned lanes) {
 (void)count;(void)lanes;++checks;
 if(scenario==2 && checks<=17) return checks<=4?0:1;
 return scenario==4 && checks==18?7:0;
}
static unsigned nb_fail(unsigned code) {return code;}
static int nb_center(unsigned lane,int tx,struct nb_window *w) {(void)lane;(void)tx;(void)w;return 1;}
static int nb_center_tx(unsigned lane,struct nb_window *rx,struct nb_window *tx) {(void)rx;return nb_center(lane,1,tx);}
static void ddrphy_training_error_write(unsigned v) {(void)v;}
static void ddrphy_training_stage_write(unsigned v) {stage=v;}
static void ddrphy_gate_override_write(unsigned v) {(void)v;}
static void ddrphy_en_vtc_write(unsigned v) {(void)v;}
static unsigned ddrphy_ready_read(void) {return 1;}
static unsigned ddrphy_vtc_rdy_read(void) {return 255;}
static void cdelay(unsigned v) {(void)v;}
''' + body + r'''
int main(void) {
 struct nb_result result;
 const char *reason[]={"","CK initialization failed: tap=16","window failed: samples=4",
   "center initialization failed: window=[0..128] center=64",
   "center burst failed: window=[0..128] center=64 errors=7"};
 for(scenario=1;scenario<=4;++scenario) {
  boots=checks=0; messages[0]=0;
  assert(nb_calibrate(&result)==(scenario==1?1:6));
  assert(strstr(messages,reason[scenario])); assert(stage==3);
 }
 scenario=0;boots=checks=0;assert(!nb_calibrate(&result));assert(stage==5);
 assert(result.ck.first==0 && result.ck.last==128 && result.ck.center==64);
 return 0;
}
''')

    def test_full_retry_bisc_and_final_memory_admission(self):
        init = function(firmware.INCLUDE / "init.h", "static int sdram_usnative_init(")
        bisc = function(firmware.INCLUDE / "init.h", "int sdram_usnative_bisc(")
        full = function(firmware.ROOT / "litex/soc/software/liblitedram/sdram.c", "int sdram_init(void)")
        source = r'''
#include <assert.h>
#include <stdio.h>
#define CONFIG_SDRAM_USNATIVE_XEM8320
#define CONFIG_SDRAM_DMA_SOFTWARE_ADMISSION
#define CSR_DDRCTRL_BASE 1
#define MAIN_RAM_BASE 0x40000000ul
#define MAIN_RAM_BASE_VA MAIN_RAM_BASE
#define MEMTEST_DATA_SIZE 64
#define USNATIVE_RDPHASE 2
#define SDRAM_PHY_WRPHASE 3
#define USNATIVE_DEBUG(...) do {} while(0)
#define USNATIVE_SNAPSHOT() do {} while(0)
#define false 0
struct nb_window {unsigned first,last,center,short_window;};
struct nb_result {struct nb_window ck,rx[2],dq[2];};
static unsigned admission=1,stage,error,bisc_only,reset,owner;
static unsigned fail_cal=1,fail_memory,calibrations,memtests,bisc_calls,bisc_ok=1;
static unsigned refine_error,refine_calls,dma_width=256;
static void dma_bench_software_ready_write(unsigned v) {admission=v;}
static unsigned dma_bench_data_width_read(void) {return dma_width;}
static void sdram_software_control_on(void) {owner=1;}
static void sdram_software_control_off(void) {owner=0;}
static unsigned sdram_get_freq(void) {return 3200000000u;}
static void cdelay(unsigned v) {(void)v;}
static void ddrphy_training_stage_write(unsigned v) {stage=v;}
static void ddrphy_training_error_write(unsigned v) {error=v;}
static unsigned ddrphy_training_error_read(void) {return error;}
static unsigned ddrphy_training_stage_read(void) {return stage;}
static void ddrctrl_init_done_write(unsigned v) {(void)v;}
static void ddrctrl_init_error_write(unsigned v) {(void)v;}
static unsigned ddrphy_dly_rdy_read(void) {return 255;}
static unsigned ddrphy_vtc_rdy_read(void) {return 255;}
static unsigned nb_fail(unsigned v) {error=v;bisc_only=reset=owner=1;return v;}
static unsigned nb_calibrate(struct nb_result *r) {
 (void)r;assert(!admission);++calibrations;
 if(fail_cal)return nb_fail(6);
 bisc_only=reset=0;stage=5;return 0;
}
static unsigned nd_calibrate(unsigned lanes,unsigned *centers) {
 (void)lanes;(void)centers;assert(!admission);return 0;
}
static unsigned nd_dma_refine(unsigned *centers) {
 (void)centers;assert(admission);++refine_calls;
 return refine_error?nb_fail(refine_error):0;
}
static int nb_bisc(void) {++bisc_calls;bisc_only=1;reset=0;return bisc_ok;}
static int memtest(unsigned *p,unsigned size) {
 (void)p;(void)size;assert(!admission && !owner);++memtests;return !fail_memory;
}
static void memspeed(unsigned *p,unsigned size,int w,int rnd) {(void)p;(void)size;(void)w;(void)rnd;}
'''
        main = r'''
int main(void) {
 assert(!sdram_init() && !admission && bisc_only && reset && calibrations==1 && !memtests);
 fail_cal=0;
 assert(sdram_init() && admission && !bisc_only && calibrations==2 && memtests==1);
 assert(sdram_usnative_bisc() && !admission && bisc_only && owner && stage==2 && bisc_calls==1);
 assert(sdram_init() && admission && calibrations==3 && memtests==2);
 fail_memory=1;assert(!sdram_init() && !admission && error==20 && reset);
 fail_memory=0;assert(sdram_init() && admission && calibrations==5 && memtests==4);
 bisc_ok=0;assert(!sdram_usnative_bisc() && !admission && reset && error==1);
 assert(sdram_init() && admission && calibrations==6);
#ifdef CONFIG_SDRAM_USNATIVE_DMA_CALIBRATION
 refine_error=17;assert(!sdram_init() && !admission && error==17);
 assert(refine_calls==6);
 unsigned prior_calibrations=calibrations;
 dma_width=128;refine_error=0;
 assert(!sdram_init() && !admission && error==21 && reset);
 assert(calibrations==prior_calibrations && refine_calls==6);
#endif
 return 0;
}
'''
        for debug, dma in ((False,False),(True,False),(False,True),(True,True)):
            with self.subTest(debug=debug, dma=dma):
                config = ("#define CONFIG_SDRAM_USNATIVE_DEBUG\n" if debug else "")
                config += ("#define CONFIG_SDRAM_USNATIVE_DMA_CALIBRATION\n" if dma else "")
                self.compile_run(config + source + init + bisc + full + main)

        self.compile_run("#define SDRAM_TEST_DISABLE\n" + source + init + full + r'''
int main(void) {
 fail_cal=0;assert(sdram_init());assert(!admission && !memtests);
 return 0;
}
''')


    def test_lane_window_failures_keep_minimum_width(self):
        body = function(firmware.INCLUDE / "native_burst_calibration.h", "static int nb_center(")
        self.compile_run(r'''
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
static char messages[4096];
static int capture(const char *format, ...) {
 va_list args;va_start(args,format);
 int n=vsnprintf(messages+strlen(messages),sizeof(messages)-strlen(messages),format,args);
 va_end(args);return n;
}
#define printf capture
#define USNATIVE_DEBUG(...) do {} while(0)
struct nb_window {unsigned first,last,center,short_window;};
static unsigned scenario,tap,programs;
static int nb_delay(unsigned lane,unsigned value,int tx) {
 assert(lane==1 && tx);tap=value;++programs;
 return !((scenario==1 && value==40) || (scenario==3 && programs==38));
}
static unsigned nb_check(unsigned count,unsigned lanes) {
 assert(lanes==2);
 if(count==256)return scenario==4?2:0;
 return tap<56 || tap>(scenario==2?84:88);
}
''' + body + r'''
int main(void) {
 const char *reasons[]={"","TX delay failed: lane=1 tap=40",
  "TX window too short: lane=1 samples=8 required=9",
  "TX center delay failed: lane=1 center=72",
  "TX center burst failed: lane=1 center=72 errors=2"};
 struct nb_window w;
 for(scenario=1;scenario<=4;++scenario) {
  programs=0;messages[0]=0;
  assert(!nb_center(1,1,&w));assert(strstr(messages,reasons[scenario]));
 }
 scenario=0;programs=0;assert(nb_center(1,1,&w));
 assert(w.first==56 && w.last==88 && w.center==72);
 return 0;
}
''')


    def test_3200_tx_retry_requires_two_wide_windows(self):
        body = function(firmware.INCLUDE / "native_burst_calibration.h", "static int nb_center_tx(")
        source = r'''
#include <assert.h>
#include <stdio.h>
#define USNATIVE_BOOT_TX_DELAY 72
struct nb_window {unsigned first,last,center,short_window;};
static unsigned scenario,scans,programs,rx_value;
static int nb_center(unsigned lane,int tx,struct nb_window *w) {
 assert(lane==0 && tx);++scans;
 w->short_window=0;
 if(scans==1) {w->short_window=scenario!=1;return 0;}
 if(scenario==2 || (scenario==6 && scans==2)) {w->short_window=1;return 0;}
 w->first=scans%2?60:56;w->last=92;w->center=76;
 if(scenario==3 && scans%2)w->first=64; /* intersection is only 28 taps */
 return 1;
}
static int nb_delay(unsigned lane,unsigned tap,int tx) {
 assert(lane==0);++programs;if(!tx)rx_value=tap;return scenario!=4;
}
static unsigned nb_check(unsigned count,unsigned lanes) {assert(count==256 && lanes==1);return 0;}
'''
        main = r'''
int main(void) {
 struct nb_window rx={24,72,48,0},tx;
#ifdef EXPECT_RETRY
 assert(nb_center_tx(0,&rx,&tx));assert(scans==3 && rx.center==52 && rx_value==52);
 assert(tx.first==60 && tx.last==92 && tx.center==76);
 for(scenario=1;scenario<=4;++scenario) {
  scans=programs=0;rx.center=48;
  assert(!nb_center_tx(0,&rx,&tx));assert(rx.center==48);
  assert(scans<=9);if(scenario==1)assert(programs==0);
 }
 scenario=6;scans=programs=0;rx.center=44;
 assert(nb_center_tx(0,&rx,&tx));assert(rx.center==52 && scans==4);
 scenario=0;scans=programs=0;rx.center=48;rx.first=44;rx.last=52;
 assert(!nb_center_tx(0,&rx,&tx));assert(scans==1 && programs==0);
#else
 assert(!nb_center_tx(0,&rx,&tx));assert(scans==1 && programs==0);
#endif
 return 0;
}
'''
        self.compile_run("#define CONFIG_CLOCK_FREQUENCY 400000000\n#define EXPECT_RETRY\n" + source + body + main)
        self.compile_run("#define CONFIG_CLOCK_FREQUENCY 333333333\n" + source + body + main)
