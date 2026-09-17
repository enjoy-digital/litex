/*
 * This file is part of LiteX.
 * SPDX-License-Identifier: BSD-2-Clause
 */

/* Per-DQ read deskew for the XEM8320 native tap-index ABI.
 * Experimental, destructive calibration; see doc/usnative_bios.md.
 */
static const unsigned nd_sites[16]={4,2,3,11,5,10,8,9,23,22,16,15,18,21,17,24};
struct nd_score {unsigned errors[16];};
static int nd_error(unsigned address,unsigned actual,unsigned expected,void *arg)
{
    struct nd_score *score=arg; unsigned diff=actual^expected; (void)address;
    for(unsigned bit=0;bit<16;++bit)
        if(diff & ((1u<<bit)|(1u<<(bit+16)))) ++score->errors[bit];
    return 0;
}
static unsigned nd_check(struct nd_score *score,unsigned readonly)
{
    struct memtest_config config;
    for(unsigned bit=0;bit<16;++bit) score->errors[bit]=0;
    config.show_progress=0;config.read_only=readonly;config.on_error=nd_error;config.arg=score;
    memtest_data((unsigned*)0x41000000,0x200000,1,&config);
    unsigned errors=0;for(unsigned bit=0;bit<16;++bit) errors+=score->errors[bit];
    return errors;
}
static int nd_program(const unsigned *centers,unsigned lane_mask,int offset)
{
    flush_cpu_dcache();flush_l2_cache();cdelay(1000);
    sdram_dfii_control_write(DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET_N);
    ddrphy_en_vtc_write(0);cdelay(1000);
    for(unsigned bit=0;bit<16;++bit) {
        if(!(lane_mask & (1u<<(bit/8)))) continue;
        int tap=(int)centers[bit]+offset;
        if(tap<0 || tap>511) return 0;
        ddrphy_tap_select_write(nd_sites[bit]);cdelay(100);
        if(!ddrphy_tap_allowed_read()) return 0;
        ddrphy_tap_rx_rst_write(1);cdelay(100);
        for(int i=0;i<tap;++i) {ddrphy_tap_rx_inc_write(1);cdelay(100);}
        if(!native_tap_wait()) return 0;
        if(ddrphy_tap_rx_count_read()!=(unsigned)tap) return 0;
    }
    sdram_software_control_off();cdelay(10000);
    return nc_wait_vtc();
}
static unsigned nd_calibrate(unsigned lane_mask,unsigned *centers)
{
    struct nd_score score;
    unsigned run[16],best[16],end[16];
    for(unsigned bit=0;bit<16;++bit) {run[bit]=0;best[bit]=0;end[bit]=0;}
    ddrphy_training_stage_write(7);sdram_software_control_off();
    /* Seeding is required even when diagnostic arguments are compiled out. */
    unsigned seed_errors=nd_check(&score,0);
    USNATIVE_DEBUG("Bit RX deskew seed errors: %u\n",seed_errors);
    (void)seed_errors;
    for(unsigned lane=0;lane<2;++lane) {
        if(!(lane_mask & (1u<<lane))) continue;
        for(unsigned tap=12;tap<=68;tap+=2) {
            if(!nc_set_rx(lane,tap)) return nb_fail(12);
            nd_check(&score,1);
            USNATIVE_DEBUG("DESKEW_SCAN lane=%u tap=%u",lane,tap);
            for(unsigned bit=lane*8;bit<lane*8+8;++bit) {
                unsigned errors=score.errors[bit];USNATIVE_DEBUG(" %u",errors);
                if(errors) run[bit]=0;else ++run[bit];
                if(run[bit]>best[bit]) {best[bit]=run[bit];end[bit]=tap;}
            }
            USNATIVE_DEBUG("\n");
        }
        for(unsigned bit=lane*8;bit<lane*8+8;++bit) {
            if(best[bit]<9) return nb_fail(13); /* >=16 measured taps per bit */
            unsigned first=end[bit]-2*(best[bit]-1);
            centers[bit]=first+2*((best[bit]-1)/2);
            USNATIVE_DEBUG("DESKEW_BIT %u WINDOW %u %u CENTER %u\n",bit,first,end[bit],centers[bit]);
        }
        if(!nd_program(centers,1u<<lane,0)) return nb_fail(12);
    }
    for(int offset=-4;offset<=4;offset+=4) {
        if(!nd_program(centers,lane_mask,offset)) return nb_fail(12);
        unsigned errors=nd_check(&score,0);
        USNATIVE_DEBUG("DESKEW_GUARD offset=%d errors=%u\n",offset,errors);
        if(errors) return nb_fail(15);
    }
    if(!nd_program(centers,lane_mask,0)) return nb_fail(12);
    unsigned errors=nd_check(&score,0);
    USNATIVE_DEBUG("DESKEW_FINAL_ERRORS %u\n",errors);
    if(errors) return nb_fail(14);
    ddrphy_training_stage_write(5);USNATIVE_SNAPSHOT();return 0;
}
