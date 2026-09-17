/*
 * This file is part of LiteX.
 * SPDX-License-Identifier: BSD-2-Clause
 */

/* Included by sdram.c so direct-DFII helpers share its generated interface. */
#include "profile.h"
#include "native_burst_calibration.h"
#include "native_controller_calibration.h"
#include "native_bit_calibration.h"
#ifdef CONFIG_SDRAM_USNATIVE_DMA_CALIBRATION
#include "native_dma_calibration.h"
#endif

static int sdram_usnative_init(void)
{
#ifdef CONFIG_SDRAM_USNATIVE_DMA_CALIBRATION
    if (dma_bench_data_width_read() != 256) {
        printf("USNative calibration requires 256-bit DMA.\n");
        nb_fail(21);
        return 0;
    }
#endif
    printf("USNativeDDRPHY: XEM8320 x16, %u MT/s, RD%u/WR%u (experimental)\n",
        sdram_get_freq()/1000000u, USNATIVE_RDPHASE, SDRAM_PHY_WRPHASE);
    printf("Standalone native burst calibration (experimental)\n");
    sdram_software_control_on();
    ddrphy_training_stage_write(1); ddrphy_training_error_write(0);
#if defined(CONFIG_SDRAM_USNATIVE_DEBUG) && defined(CSR_DDRPHY_DEBUG_CLEAR_ADDR)
    ddrphy_debug_clear_write(1);
#endif
    cdelay(1000);
    struct nb_result result;
    unsigned error=nb_calibrate(&result);
    if (error) {
        printf("Native calibration failed: stage=%u error=%u\n",
            (unsigned)ddrphy_training_stage_read(), error);
        return 0;
    }
    unsigned rx_centers[16];
    error=nd_calibrate(3,rx_centers);
    if (error) {
        printf("Controller per-bit RX deskew failed: error=%u\n",error);
        return 0;
    }
#ifdef CONFIG_SDRAM_USNATIVE_DMA_CALIBRATION
    /* Only explicitly requested internal training may use DMA before the
     * final CPU memory test. Revoke admission on both success and failure. */
#ifdef CONFIG_SDRAM_DMA_SOFTWARE_ADMISSION
    dma_bench_software_ready_write(1);
#endif
    error=nd_dma_refine(rx_centers);
#ifdef CONFIG_SDRAM_DMA_SOFTWARE_ADMISSION
    dma_bench_software_ready_write(0);
#endif
    if(error) {
        printf("Native DMA RX refinement failed: error=%u\n",error);
        return 0;
    }
#endif
    USNATIVE_DEBUG("Native CK window [%u..%u], selected %u taps\n",
        result.ck.first,result.ck.last,result.ck.center);
    for (unsigned lane=0; lane<2; ++lane) {
        USNATIVE_DEBUG("Native lane %u direct RX [%u..%u] -> %u (superseded by per-bit deskew), DQ/DM [%u..%u] -> %u, DQS 68\n",
            lane,result.rx[lane].first,result.rx[lane].last,result.rx[lane].center,
            result.dq[lane].first,result.dq[lane].last,result.dq[lane].center);
    }
#ifdef CONFIG_SDRAM_USNATIVE_DMA_CALIBRATION
    printf("Native DMA refinement PASS.\n");
#endif
    printf("Native calibration PASS: direct bursts, per-bit RX deskew and +/-4-tap guards; BIOS memory test follows.\n");
    return 1;
}

#ifdef CONFIG_SDRAM_USNATIVE_DEBUG
/* An explicit diagnostic operation, never inferred from a previous failure.
 * A BISC pass says nothing about DDR: retain software ownership and DDR reset. */
int sdram_usnative_bisc(void)
{
#ifdef CONFIG_SDRAM_DMA_SOFTWARE_ADMISSION
    dma_bench_software_ready_write(0);
#endif
#ifdef CSR_DDRCTRL_BASE
    ddrctrl_init_done_write(0);
    ddrctrl_init_error_write(0);
#endif
    sdram_software_control_on();
    ddrphy_training_stage_write(1);
    ddrphy_training_error_write(0);
    printf("USNative BISC-only diagnostic: DDR held reset; no memory training/test.\n");
    if (!nb_bisc()) {
        nb_fail(1);
        printf("Native BISC timeout: DLY=%02x VTC=%02x\n",
            (unsigned)ddrphy_dly_rdy_read(), (unsigned)ddrphy_vtc_rdy_read());
        return 0;
    }
    ddrphy_training_stage_write(2);
    USNATIVE_SNAPSHOT();
    printf("Native BISC PASS: DLY=%02x VTC=%02x; DDR/DMA remain unavailable.\n",
        (unsigned)ddrphy_dly_rdy_read(), (unsigned)ddrphy_vtc_rdy_read());
    return 1;
}
#endif
