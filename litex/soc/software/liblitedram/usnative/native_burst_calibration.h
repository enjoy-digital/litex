/*
 * This file is part of LiteX.
 * SPDX-License-Identifier: BSD-2-Clause
 */

/* Direct-DFII clock, read and write window searches for the XEM8320 x16 profile.
 * Experimental, destructive calibration; see doc/usnative_bios.md.
 */
#ifndef XEM8320_NATIVE_BURST_CALIBRATION_H
#define XEM8320_NATIVE_BURST_CALIBRATION_H
#include <generated/csr.h>
#include <generated/sdram_phy.h>
#include "native_status_io.h"

struct nb_window { unsigned first, last, center, short_window; };
struct nb_result { struct nb_window ck, rx[2], dq[2]; };

static unsigned nb_fail(unsigned error)
{
    sdram_software_control_on();
    ddrphy_training_error_write(error);
    ddrphy_bisc_only_write(1);
    ddrphy_rst_write(1);
    return error;
}

static int nb_bisc(void)
{
    ddrphy_bisc_only_write(1); ddrphy_rst_write(1);
    ddrphy_en_vtc_write(1); ddrphy_wlevel_en_write(0);
    sdram_dfii_control_write(0); cdelay(100000);
    ddrphy_rst_write(0);
    for (unsigned i=0; i<100000; ++i) {
        if (ddrphy_ready_read()) return 1;
        cdelay(100);
    }
    return 0;
}

static int nb_gate(unsigned nibble)
{
    unsigned actual;
    if (!native_riu_access(nibble, 0x30, 6<<9, 1, &actual)) return 0;
    if (!native_riu_access(nibble, 0x30, 0, 0, &actual)) return 0;
    return (actual & 0x1fff) == (6<<9);
}

static int nb_delay(unsigned lane, unsigned value, int transmit)
{
    ddrphy_dly_sel_write(1<<lane);
    if (transmit) ddrphy_wdly_dq_rst_write(1);
    else ddrphy_rdly_dq_rst_write(1);
    cdelay(100);
    for (unsigned i=0; i<value; ++i) {
        if (transmit) ddrphy_wdly_dq_inc_write(1);
        else ddrphy_rdly_dq_inc_write(1);
        cdelay(100);
    }
    ddrphy_tap_select_write(lane ? 23 : 4); cdelay(100);
    if (!native_tap_wait()) return 0;
    return (transmit ? ddrphy_tap_tx_count_read() : ddrphy_tap_rx_count_read())==value;
}

static int nb_boot(unsigned ck)
{
    if (!nb_bisc()) return 0;
    ddrphy_en_vtc_write(0); cdelay(1000);
    ddrphy_cdly_rst_write(1); cdelay(100);
    for (unsigned i=0; i<ck; ++i) { ddrphy_cdly_inc_write(1); cdelay(100); }
    ddrphy_tap_select_write(39); cdelay(100);
    if (!native_tap_wait()) return 0;
    if (ddrphy_tap_tx_count_read()!=ck) return 0;
    /* Clock moves only while the device is held reset. */
    ddrphy_bisc_only_write(0); init_sequence(); cdelay(10000);
    ddrphy_rdphase_write(USNATIVE_RDPHASE); ddrphy_wrphase_write(SDRAM_PHY_WRPHASE);
    ddrphy_tx_dqs_pre_write(0x55); ddrphy_tx_dqs_post_write(0x55);
    ddrphy_tx_dqs_idle_write(0x55);
    ddrphy_dly_sel_write(3);
    ddrphy_rdly_dq_bitslip_rst_write(1); ddrphy_wdly_dq_bitslip_rst_write(1);
    ddrphy_gate_delay_write(USNATIVE_GATE_DELAY); ddrphy_gate_override_write(3);
    ddrphy_gate_delay0_write(USNATIVE_GATE_DELAY); ddrphy_gate_delay1_write(USNATIVE_GATE_DELAY);
    ddrphy_gate_width0_write(1); ddrphy_gate_width1_write(1);
    ddrphy_fifo_lane_mode_write(0);
    for (unsigned n=0; n<4; ++n) if (!nb_gate(n)) return 0;
    ddrphy_dly_sel_write(3); ddrphy_wdly_dqs_rst_write(1); cdelay(100);
    for (unsigned i=0; i<68; ++i) { ddrphy_wdly_dqs_inc_write(1); cdelay(100); }
    for (unsigned lane=0; lane<2; ++lane) {
        ddrphy_dly_sel_write(1<<lane); cdelay(100);
        if (ddrphy_wdly_dqs_inc_count_read()!=68) return 0;
        if (!nb_delay(lane,USNATIVE_BOOT_TX_DELAY,1) || !nb_delay(lane,USNATIVE_BOOT_RX_DELAY,0)) return 0;
    }
    return 1;
}

static unsigned nb_check(unsigned count, unsigned lanes)
{
    unsigned errors=0;
    unsigned mask=(lanes&1 ? 0x00ff00ff : 0) | (lanes&2 ? 0xff00ff00 : 0);
    /* Replace startup FIFO contents before scoring a new delay point. */
    for (unsigned i=0; i<count+8; ++i) {
        unsigned q0=0x12345678^(i*0x1020304), q1=0xa55a5aa5^(i*0x01010101);
        unsigned q2=0xdeadbeef+i, q3=0x55aa00ff-i;
        sdram_dfii_pi0_address_write(i*64); sdram_dfii_pi0_baddress_write(0);
        command_p0(DFII_COMMAND_RAS|DFII_COMMAND_CS); cdelay(1000);
        sdram_dfii_pi0_wrdata_write(q0); sdram_dfii_pi1_wrdata_write(q1);
        sdram_dfii_pi2_wrdata_write(q2); sdram_dfii_pi3_wrdata_write(q3);
        sdram_dfii_pi0_address_write((i*8)&0x3ff);
        USNATIVE_WR_ADDRESS((i*8)&0x3ff); USNATIVE_WR_BANK(0);
        USNATIVE_WR_COMMAND(DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS|DFII_COMMAND_WRDATA);
        cdelay(1000);
        USNATIVE_RD_ADDRESS((i*8)&0x3ff); USNATIVE_RD_BANK(0);
        USNATIVE_RD_COMMAND(DFII_COMMAND_CAS|DFII_COMMAND_CS|DFII_COMMAND_RDDATA); cdelay(1000);
        unsigned wrong=(sdram_dfii_pi0_rddata_read()^q0) | (sdram_dfii_pi1_rddata_read()^q1) |
            (sdram_dfii_pi2_rddata_read()^q2) | (sdram_dfii_pi3_rddata_read()^q3);
        if (i>=8 && (wrong&mask)) ++errors;
        sdram_dfii_pi0_address_write(1<<10);
        command_p0(DFII_COMMAND_RAS|DFII_COMMAND_WE|DFII_COMMAND_CS); cdelay(1000);
    }
    return errors;
}

static int nb_center(unsigned lane, int transmit, struct nb_window *window)
{
    unsigned start=transmit ? 32 : 0, end=transmit ? 176 : 128;
    unsigned run=0, best=0, best_end=0;
    const char *direction=transmit ? "TX" : "RX";
    window->short_window=0;
    for (unsigned tap=start; tap<=end; tap+=4) {
        if (!nb_delay(lane,tap,transmit)) {
            printf("Native %s delay failed: lane=%u tap=%u\n",direction,lane,tap);
            return 0;
        }
        if (nb_check(128,1<<lane)) run=0; else ++run;
        if (run>best) { best=run; best_end=tap; }
    }
    if (best<9) { /* Require at least 32 taps of measured width. */
        window->short_window=1;
        printf("Native %s window too short: lane=%u samples=%u required=9 step=4 first=%u last=%u\n",
            direction,lane,best,best ? best_end-4*(best-1) : 0,best_end);
        return 0;
    }
    window->first=best_end-4*(best-1); window->last=best_end;
    window->center=window->first+4*((best-1)/2);
    if (!nb_delay(lane,window->center,transmit)) {
        printf("Native %s center delay failed: lane=%u center=%u\n",direction,lane,window->center);
        return 0;
    }
    unsigned errors=nb_check(256,1<<lane);
    USNATIVE_DEBUG("NATIVE_WINDOW direction=%s lane=%u first=%u last=%u center=%u errors=%u\n",
        direction,lane,window->first,window->last,window->center,errors);
    if (errors) {
        printf("Native %s center burst failed: lane=%u center=%u errors=%u\n",
            direction,lane,window->center,errors);
        return 0;
    }
    return 1;
}

/* At 3200, a read sampling point can limit the observed write window.
 * Retry only an undersized window, at four nearby RX points inside its measured
 * bounds. Accept an intersection of two complete TX scans, never a relaxed
 * width or a failed delay/center confirmation. Other profiles are unchanged. */
static int nb_center_tx(unsigned lane, struct nb_window *rx, struct nb_window *tx)
{
    if (nb_center(lane,1,tx)) return 1;
#if CONFIG_CLOCK_FREQUENCY == 400000000
    if (!tx->short_window) return 0;
    const int offsets[4]={4,8,-4,-8};
    for (unsigned attempt=0; attempt<4; ++attempt) {
        int candidate=(int)rx->center+offsets[attempt];
        if (candidate<(int)rx->first+4 || candidate>(int)rx->last-4) continue;
        printf("Native TX window retry: lane=%u attempt=%u RX=%d\n",lane,attempt+1,candidate);
        if (!nb_delay(lane,USNATIVE_BOOT_TX_DELAY,1) ||
            !nb_delay(lane,(unsigned)candidate,0)) return 0;
        if (nb_check(256,1<<lane)) continue;
        if (!nb_center(lane,1,tx)) {
            if (!tx->short_window) return 0;
            continue;
        }
        struct nb_window confirm;
        if (!nb_center(lane,1,&confirm)) {
            if (!confirm.short_window) return 0;
            continue;
        }
        unsigned first=tx->first>confirm.first ? tx->first : confirm.first;
        unsigned last=tx->last<confirm.last ? tx->last : confirm.last;
        if (last<first || last-first<32) continue;
        tx->first=first; tx->last=last; tx->center=first+4*((last-first)/8);
        if (!nb_delay(lane,tx->center,1) || nb_check(256,1<<lane)) return 0;
        rx->center=(unsigned)candidate;
        printf("Native TX retry accepted: lane=%u RX=%u TX=[%u..%u] center=%u\n",
            lane,rx->center,tx->first,tx->last,tx->center);
        return 1;
    }
#endif
    return 0;
}

/* Return zero only after margin searches and a VTC-enabled burst check.
 * DFI remains under software ownership; controller memtest is a separate
 * acceptance step performed by the caller after successful calibration. */
static unsigned nb_calibrate(struct nb_result *result)
{
    unsigned run=0, best=0, best_end=0;
    ddrphy_training_error_write(0); ddrphy_training_stage_write(3);
    for (unsigned ck=0; ck<=128; ck+=8) {
        if (!nb_boot(ck)) {
            printf("Native CK initialization failed: tap=%u\n",ck);
            return nb_fail(1);
        }
        unsigned errors=nb_check(256,3);
        USNATIVE_DEBUG("NATIVE_CK tap=%u errors=%u\n",ck,errors);
        if (errors) run=0; else ++run;
        if (run>best) { best=run; best_end=ck; }
    }
    if (best<5) {
        printf("Native CK window failed: samples=%u last=%u required=5 step=8\n",best,best_end);
        return nb_fail(6);
    }
    result->ck.first=best_end-8*(best-1); result->ck.last=best_end;
    result->ck.center=result->ck.first+8*((best-1)/2);
    if (!nb_boot(result->ck.center)) {
        printf("Native CK center initialization failed: window=[%u..%u] center=%u\n",
            result->ck.first,result->ck.last,result->ck.center);
        return nb_fail(6);
    }
    unsigned errors=nb_check(256,3);
    if (errors) {
        printf("Native CK center burst failed: window=[%u..%u] center=%u errors=%u\n",
            result->ck.first,result->ck.last,result->ck.center,errors);
        return nb_fail(6);
    }
    ddrphy_training_stage_write(4);
    for (unsigned lane=0; lane<2; ++lane)
        if (!nb_center(lane,0,&result->rx[lane])) return nb_fail(7);
    for (unsigned lane=0; lane<2; ++lane)
        if (!nb_center_tx(lane,&result->rx[lane],&result->dq[lane])) return nb_fail(8);
    if (nb_check(4096,3)) return nb_fail(9);
    ddrphy_gate_override_write(0); ddrphy_en_vtc_write(1);
    unsigned i;
    for (i=0; i<100000; ++i) {
        if (ddrphy_ready_read() && ddrphy_vtc_rdy_read()==255) break;
        cdelay(100);
    }
    if (i==100000) return nb_fail(5);
    if (nb_check(256,3)) return nb_fail(9);
    ddrphy_training_stage_write(5); USNATIVE_SNAPSHOT();
    return 0;
}
#endif
