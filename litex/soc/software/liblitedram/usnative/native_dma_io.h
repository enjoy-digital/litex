/*
 * This file is part of LiteX.
 * SPDX-License-Identifier: BSD-2-Clause
 */

/* Counter/PRBS DMA refinement and measured per-bit guard margins.
 * Experimental, destructive calibration; see doc/usnative_bios.md.
 */
#ifndef __USNATIVE_DMA_IO_H
#define __USNATIVE_DMA_IO_H
static unsigned nd_dma_check(unsigned random,unsigned readonly)
{
    flush_cpu_dcache();flush_l2_cache();
    if(dma_bench_busy_read() || dma_bench_fault_read()>=3) return 0xffffffffu;
    dma_bench_base_write(0x01000000);dma_bench_length_write(0x04000000);
    dma_bench_random_write(random);dma_bench_read_only_write(readonly);
    dma_bench_timeout_write(1000000000);dma_bench_start_write(1);
    /* Hardware timeout cannot cover a lost done response; also bound polling. */
    unsigned polls;
    for (polls=0; polls<USNATIVE_DMA_POLL_LIMIT; ++polls) {
        if (dma_bench_done_read()) break;
        cdelay(1);
    }
    if (polls==USNATIVE_DMA_POLL_LIMIT) return 0xffffffffu;
    if(dma_bench_fault_read() || dma_bench_read_beats_read()!=0x200000 ||
       dma_bench_write_beats_read()!=(readonly?0:0x200000)) return 0xffffffffu;
    return dma_bench_errors_read();
}
#endif
