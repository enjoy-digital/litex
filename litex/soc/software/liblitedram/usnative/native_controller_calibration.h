/*
 * This file is part of LiteX.
 * SPDX-License-Identifier: BSD-2-Clause
 */

/* Controller-based read-window helpers; execution must remain in ROM/SRAM.
 * Experimental, destructive calibration; see doc/usnative_bios.md.
 */
#include <libbase/memtest.h>
#include <system.h>
static int nc_wait_vtc(void)
{
    /* Poll real readiness after tap changes; CPU speed must not decide success. */
    for (unsigned attempt=0;attempt<1000;++attempt) {
        if (ddrphy_ready_read() && ddrphy_vtc_rdy_read()==255) return 1;
        cdelay(1000);
    }
    return 0;
}
static int nc_set_rx(unsigned lane, unsigned tap)
{
    flush_cpu_dcache(); flush_l2_cache(); cdelay(1000);
    ddrphy_en_vtc_write(0); cdelay(1000);
    if (!nb_delay(lane,tap,0)) return 0;
    ddrphy_en_vtc_write(1); cdelay(10000);
    return nc_wait_vtc();
}
