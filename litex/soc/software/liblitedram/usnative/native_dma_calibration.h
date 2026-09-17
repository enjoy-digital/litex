/*
 * This file is part of LiteX.
 * SPDX-License-Identifier: BSD-2-Clause
 */

/* Counter/PRBS DMA refinement and measured per-bit guard margins.
 * Experimental, destructive calibration; see doc/usnative_bios.md.
 */
#include "native_dma_io.h"

/* A global read-only sweep can disagree with fresh guarded traffic. On guard
 * exhaustion only, measure the failing DQs with all other DQs held at
 * their selected centers. Intersect two opposite-direction scans and both
 * patterns; never enlarge a window by extrapolating beyond passing samples. */
static unsigned nd_dma_rescan(unsigned *centers, unsigned mask,
    unsigned *window_first, unsigned *window_last)
{
    for(unsigned bit=0;bit<16;++bit) if(mask & (1u<<bit)) {
        unsigned clean[29],trial[16];
        for(unsigned sample=0;sample<29;++sample) clean[sample]=1;
        for(unsigned pass=0;pass<2;++pass) {
            for(unsigned step=0;step<29;++step) {
                unsigned sample=pass?28-step:step;
                for(unsigned dq=0;dq<16;++dq) trial[dq]=centers[dq];
                trial[bit]=12+2*sample;
                if(!nd_program(trial,3,0)) return 12;
                for(unsigned pattern=0;pattern<2;++pattern) {
                    unsigned errors=nd_dma_check(pattern,0);
                    unsigned observed=dma_bench_dq_error_mask_read();
                    USNATIVE_DEBUG("DMA_RESCAN bit=%u pass=%u tap=%u pattern=%u errors=%u mask=%04x\n",
                        bit,pass,trial[bit],pattern,errors,observed);
                    if(errors==0xffffffffu || (!!errors != !!observed)) return 16;
                    if(observed & (1u<<bit)) clean[sample]=0;
                }
            }
        }
        unsigned run=0,best=0,end=0;
        for(unsigned sample=0;sample<29;++sample) {
            if(clean[sample]) ++run; else run=0;
            if(run>best) {best=run;end=12+2*sample;}
        }
        if(best<5) {
            USNATIVE_DEBUG("DMA_RESCAN_NO_WINDOW bit=%u samples=%u\n",bit,best);
            return 17;
        }
        window_first[bit]=end-2*(best-1);window_last[bit]=end;
        centers[bit]=window_first[bit]+2*((best-1)/2);
        USNATIVE_DEBUG("DMA_RESCAN_WINDOW bit=%u first=%u last=%u center=%u\n",
            bit,window_first[bit],end,centers[bit]);
        if(!nd_program(centers,3,0)) return 12;
    }
    return 0;
}

static unsigned nd_dma_refine(unsigned *centers)
{
    /* Score physical bits independently over the complete DMA transfer.
     * Counter and PRBS eyes must overlap; aggregate errors are diagnostic
     * only and never used to score a different DQ. */
    unsigned clean[29],trial[16],window_first[16],window_last[16];
    for(unsigned sample=0;sample<29;++sample) clean[sample]=0xffff;
    for(unsigned pattern=0;pattern<2;++pattern) {
        if(!nd_program(centers,3,0)) return nb_fail(12);
        unsigned seed=nd_dma_check(pattern,0);
        USNATIVE_DEBUG("DMA deskew seed pattern=%u errors=%u mask=%04x\n",
            pattern, seed, (unsigned)dma_bench_dq_error_mask_read());
        if(seed==0xffffffffu || (!!seed != !!dma_bench_dq_error_mask_read())) return nb_fail(16);
        for(unsigned sample=0;sample<29;++sample) {
            unsigned tap=12+2*sample;
            for(unsigned bit=0;bit<16;++bit) trial[bit]=tap;
            if(!nd_program(trial,3,0)) return nb_fail(12);
            unsigned errors=nd_dma_check(pattern,1);
            unsigned mask=dma_bench_dq_error_mask_read();
            USNATIVE_DEBUG("DMA_DESKEW_MASK pattern=%u tap=%u errors=%u mask=%04x\n",pattern,tap,errors,mask);
            if(errors==0xffffffffu || (!!errors != !!mask)) return nb_fail(16);
            clean[sample] &= ~mask;
        }
    }
    for(unsigned bit=0;bit<16;++bit) {
        unsigned run=0,best=0,end=0;
        for(unsigned sample=0;sample<29;++sample) {
            if(clean[sample] & (1u<<bit)) ++run;else run=0;
            if(run>best) {best=run;end=12+2*sample;}
        }
        if(best<5) {USNATIVE_DEBUG("DMA_DESKEW_NO_WINDOW bit=%u span=%u\n",bit,best?2*(best-1):0);return nb_fail(17);}
        unsigned first=end-2*(best-1);
        centers[bit]=first+2*((best-1)/2);
        window_first[bit]=first;window_last[bit]=end;
        USNATIVE_DEBUG("DMA_DESKEW_INITIAL %u WINDOW %u %u CENTER %u\n",bit,first,end,centers[bit]);
    }
    /* Refine a guard edge without reducing its required margin. Every
     * adjustment stays inside the measured counter/PRBS window, and all
     * six fresh guard transfers restart after any adjustment. */
    unsigned accepted=0,rescanned=0,affected=0;
#ifdef CONFIG_SDRAM_USNATIVE_DEBUG
    unsigned guard_errors[6],guard_masks[6],accepted_attempt=0;
#endif
    for(unsigned attempt=0;attempt<16 && !accepted;++attempt) {
        unsigned retry=0;
        for(int offset=-4;offset<=4 && !retry;offset+=4) {
            if(!nd_program(centers,3,offset)) return nb_fail(12);
            for(unsigned random=0;random<2;++random) {
                unsigned errors=nd_dma_check(random,0);
                unsigned mask=dma_bench_dq_error_mask_read();
#ifdef CONFIG_SDRAM_USNATIVE_DEBUG
                unsigned slot=(unsigned)(offset+4)/4*2+random;
                guard_errors[slot]=errors;guard_masks[slot]=mask;
#endif
                USNATIVE_DEBUG("DMA_GUARD_SEARCH attempt=%u offset=%d pattern=%u errors=%u mask=%04x\n",attempt,offset,random,errors,mask);
                if(errors==0xffffffffu || (!!errors != !!mask)) return nb_fail(16);
                if(errors) {
                    affected |= mask;
                    unsigned exhausted=(offset==0 || (!rescanned && attempt==7));
                    for(unsigned bit=0;bit<16;++bit) if(mask & (1u<<bit)) {
                        int next=(int)centers[bit]+(offset<0?2:-2);
                        if(next-4<(int)window_first[bit] || next+4>(int)window_last[bit]) {
                            USNATIVE_DEBUG("DMA_GUARD_WINDOW_EXHAUSTED bit=%u center=%u\n",bit,centers[bit]);
                            exhausted=1;
                        }
                    }
                    if(exhausted) {
                        if(rescanned) return nb_fail(18);
                        /* One recovery budget for the complete refinement.
                         * Include DQs implicated by earlier guard attempts. */
                        rescanned=1;
                        USNATIVE_DEBUG("DMA_GUARD_RESCAN offset=%d pattern=%u mask=%04x\n",offset,random,affected);
                        unsigned failure=nd_dma_rescan(centers,affected,window_first,window_last);
                        if(failure) return nb_fail(failure);
                    } else {
                        for(unsigned bit=0;bit<16;++bit) if(mask & (1u<<bit)) {
                            int next=(int)centers[bit]+(offset<0?2:-2);
                            USNATIVE_DEBUG("DMA_GUARD_ADJUST bit=%u old=%u new=%d\n",bit,centers[bit],next);
                            centers[bit]=(unsigned)next;
                        }
                    }
                    retry=1;break;
                }
            }
        }
        if(!retry) {
            accepted=1;
#ifdef CONFIG_SDRAM_USNATIVE_DEBUG
            accepted_attempt=attempt;
#endif
        }
    }
    if(!accepted) return nb_fail(18);
#ifdef CONFIG_SDRAM_USNATIVE_DEBUG
    USNATIVE_DEBUG("DMA_GUARD_ACCEPT attempt=%u\n",accepted_attempt);
    for(unsigned bit=0;bit<16;++bit)
        USNATIVE_DEBUG("DMA_DESKEW_BIT %u WINDOW %u %u CENTER %u\n",bit,window_first[bit],window_last[bit],centers[bit]);
    for(int offset=-4;offset<=4;offset+=4) for(unsigned random=0;random<2;++random) {
        unsigned slot=(unsigned)(offset+4)/4*2+random;
        USNATIVE_DEBUG("DMA_DESKEW_GUARD offset=%d pattern=%u errors=%u mask=%04x\n",offset,random,guard_errors[slot],guard_masks[slot]);
    }
#endif
    if(!nd_program(centers,3,0)) return nb_fail(12);
    for(unsigned random=0;random<2;++random) {
        unsigned errors=nd_dma_check(random,0);
        unsigned mask=dma_bench_dq_error_mask_read();
        USNATIVE_DEBUG("DMA_DESKEW_FINAL pattern=%u errors=%u mask=%04x\n",random,errors,mask);
        if(errors==0xffffffffu || (!!errors != !!mask)) return nb_fail(16);
        if(errors) return nb_fail(19);
    }
    ddrphy_training_stage_write(5);USNATIVE_SNAPSHOT();
    return 0;
}
