/*
 * This file is part of LiteX.
 * SPDX-License-Identifier: BSD-2-Clause
 */

/* Bounded RIU transactions and tap-status freshness for related sys:riu clocks.
 * Experimental, destructive calibration; see doc/usnative_bios.md.
 */
#ifndef XEM_NATIVE_STATUS_IO_H
#define XEM_NATIVE_STATUS_IO_H
static int native_riu_wait_idle(void)
{
    for (unsigned i=0; i<10000; ++i) {
        if (!ddrphy_riu_busy_read()) return 1;
        cdelay(10);
    }
    return 0;
}
static int native_riu_access(unsigned nibble, unsigned address, unsigned data,
                             int write, unsigned *result)
{
    if (nibble>=8 || address>=64 || !native_riu_wait_idle()) return 0;
    ddrphy_riu_nibble_write(nibble); ddrphy_riu_address_write(address);
    ddrphy_riu_wdata_write(data);
    if (write) ddrphy_riu_write_write(1); else ddrphy_riu_read_write(1);
    /* Allow the existing CPU->sys CSR pulse bridge to deliver this request.
     * Hardware clears old valid when accepting it; polling starts afterwards. */
    cdelay(100);
    if (!native_riu_wait_idle() || ddrphy_riu_error_read() || !ddrphy_riu_valid_read()) return 0;
    *result=ddrphy_riu_rdata_read();
    return 1;
}
static int native_tap_wait(void)
{
    /* The selection/control CSR update first crosses to sys, then invalidates
     * the registered status tree. Do not accept the preceding selection. */
    cdelay(100);
    for (unsigned i=0; i<10000; ++i) {
        if (ddrphy_tap_status_valid_read()) return 1;
        cdelay(10);
    }
    return 0;
}
#endif
