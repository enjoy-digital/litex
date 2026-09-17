#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

"""Execute DMA calibration against traffic-dependent and unstable DQ windows."""
import unittest

from test.software import test_usnative as firmware


@unittest.skipUnless(firmware.CC, "Host C compiler required")
class TestUSNativeDMACalibration(unittest.TestCase):
    compile_run = firmware.TestUSNativeFirmware.compile_run

    def test_per_bit_rescan_intersection_bounds_and_failures(self):
        self.compile_run(r'''
#include <assert.h>
#include <string.h>
#define __USNATIVE_DMA_IO_H
#define USNATIVE_DEBUG(...) do {} while(0)
#define USNATIVE_SNAPSHOT() do {} while(0)
static unsigned taps[16], calls, mask, scenario, stage, programmed;
static unsigned nd_program(unsigned *centers,unsigned lanes,int offset) {
 assert(lanes==3); ++programmed;
 for(unsigned bit=0;bit<16;++bit) taps[bit]=centers[bit]+offset;
 return !(scenario==4 && programmed==3);
}
static unsigned nb_fail(unsigned error) {return error;}
static void ddrphy_training_stage_write(unsigned value) {stage=value;}
static unsigned dma_bench_dq_error_mask_read(void) {return mask;}
static unsigned nd_dma_check(unsigned pattern,unsigned readonly) {
 assert(!readonly); assert(pattern==calls%2); ++calls;
 /* The other selected DQ centers must never follow the swept DQ. */
 assert(taps[0]==40 && taps[10]==38 && taps[12]==42);
 unsigned first=calls<=58?22:26, last=calls<=58?34:38;
 if(scenario==1) {first=calls<=58?22:36;last=calls<=58?34:48;}
 if(scenario==2 && calls==9) return 0xffffffffu;
 if(scenario==3 && calls==9) {mask=0;return 1;}
 if(scenario==5) {first=22;last=34;}
 mask=(taps[11]<first || taps[11]>last)?1u<<11:0;
 return !!mask;
}
#include "native_dma_calibration.h"
int main(void) {
 unsigned centers[16],first[16]={0},last[16]={0};
 for(scenario=0;scenario<6;++scenario) {
  for(unsigned bit=0;bit<16;++bit) centers[bit]=40;
  centers[10]=38;centers[12]=42;centers[11]=28;
  calls=mask=programmed=0;
  unsigned result=nd_dma_rescan(centers,1u<<11,first,last);
  if(scenario==1) assert(result==17 && calls==116);
  else if(scenario==2 || scenario==3) assert(result==16 && calls==9);
  else if(scenario==4) assert(result==12 && calls==4);
  else {
   assert(result==0 && calls==116);
   assert(first[11]==(scenario==5?22:26) && last[11]==34);
   assert(centers[11]==(scenario==5?28:30));
   assert(centers[11]-4>=first[11] && centers[11]+4<=last[11]);
   assert(taps[11]==centers[11]);
  }
 }
 return 0;
}
''')

    def test_guard_restarts_and_only_one_rescan_is_allowed(self):
        self.compile_run(r'''
#include <assert.h>
#define __USNATIVE_DMA_IO_H
#define USNATIVE_DEBUG(...) do {} while(0)
#define USNATIVE_SNAPSHOT() do {} while(0)
static unsigned taps[16],mask,readonly_calls,fresh_calls,stage,scenario,guard_calls;
static int programmed_offset;
static unsigned nd_program(unsigned *centers,unsigned lanes,int offset) {
 assert(lanes==3);programmed_offset=offset;
 for(unsigned bit=0;bit<16;++bit) taps[bit]=centers[bit]+offset;
 return 1;
}
static unsigned nb_fail(unsigned error) {return error;}
static void ddrphy_training_stage_write(unsigned value) {stage=value;}
static unsigned dma_bench_dq_error_mask_read(void) {return mask;}
static unsigned nd_dma_check(unsigned pattern,unsigned readonly) {
 (void)pattern;mask=0;
 if(readonly) {
  ++readonly_calls;
  if(taps[11]<22 || taps[11]>34) mask=1u<<11;
  if((scenario==2 || scenario==4) && (taps[14]<22 || taps[14]>36)) mask|=1u<<14;
 } else {
  ++fresh_calls;
  if(readonly_calls<58) return 0; /* Two initial reference writes. */
  unsigned first=(scenario==4 && taps[14]==34)?42:30,last=42;
  if(scenario==1) {first=22;last=34;}
  if(programmed_offset) {
   ++guard_calls;
   if(scenario==1 && programmed_offset<0) mask=1u<<11;
  }
  if(taps[11]<first || taps[11]>last) mask|=1u<<11;
  if(scenario==2 || scenario==4) {
   unsigned low=scenario==4?28:26;
   if(taps[14]<low || taps[14]>low+12) mask|=1u<<14;
   if(programmed_offset && guard_calls<=3) {
    const unsigned observed[]={0x4000,0x4800,0x0800};
    mask=observed[guard_calls-1];
   }
  }
 }
 if(scenario==3 && fresh_calls==127) {mask=1u<<11;return 0;}
 return !!mask;
}
#include "native_dma_calibration.h"
int main(void) {
 for(scenario=0;scenario<5;++scenario) {
  unsigned centers[16];for(unsigned bit=0;bit<16;++bit) centers[bit]=32;
  mask=readonly_calls=fresh_calls=stage=guard_calls=0;
  unsigned result=nd_dma_refine(centers);
  assert(readonly_calls==58);
  if(!scenario) {
   assert(!result && stage==5 && centers[11]==36);
   assert(fresh_calls==128 && guard_calls==6);
  } else if(scenario==2) {
   /* Replay the hardware masks: bit14, then11+14, then11 exhausted.
    * Both implicated DQs must be rescanned, even though only11 exhausted. */
   assert(!result && stage==5 && centers[11]==36 && centers[14]==32);
   assert(fresh_calls==245 && guard_calls==7);
  } else if(scenario==3) {
   assert(result==16 && !stage && fresh_calls==127);
  } else if(scenario==4) {
   /* Moving DQ14 to34 invalidates the earlier DQ11 measurement.
    * The post-rescan guards must detect the coupling and deny success. */
   assert(result==18 && !stage && centers[14]==34 && centers[11]==36);
   assert(fresh_calls>232 && fresh_calls<260);
  } else {
   /* 22..34 permits centers 26..30, never 32. No second rescan. */
   assert(result==18 && !stage && centers[11]==30);
   assert(fresh_calls==122 && guard_calls==4);
  }
 }
 return 0;
}
''')
