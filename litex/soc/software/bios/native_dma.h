/*
 * This file is part of LiteX.
 * SPDX-License-Identifier: BSD-2-Clause
 */

/* BIOS command: native-port DMA test; execution and stack remain in ROM/SRAM.
 * CPU caches must be flushed before DMA, and CPU must not access the test
 * region until completion. Rates use hardware cycles, not UART/CPU timing.
 */
#include <system.h>
#include <libbase/timeout.h>
#include <generated/soc.h>
#include <generated/sdram_phy.h>
#include "native_dma_admission.h"
#include "native_dma_mode.h"
#include "native_dma_timeout.h"
static void native_dma_rate(const char *direction,unsigned beats,unsigned cycles)
{
    unsigned bytes_per_beat=dma_bench_data_width_read()/8;
    uint64_t bytes=(uint64_t)beats*bytes_per_beat;
    if(!cycles) {printf("DMA %s: no transfers\n",direction);return;}
    uint64_t bps=bytes*CONFIG_CLOCK_FREQUENCY/cycles;
    uint64_t mib100=bps*100/1048576;
    unsigned peak_bytes_per_cycle=SDRAM_PHY_DATABITS*SDRAM_PHY_XDR*SDRAM_PHY_PHASES/8;
    unsigned utilization=(unsigned)(bytes*10000/((uint64_t)cycles*peak_bytes_per_cycle));
    printf("DMA %s: beats=%u cycles=%u, %u.%03u MB/s, %u.%02u MiB/s, %u.%02u%% DDR theoretical peak\n",
        direction,beats,cycles,(unsigned)(bps/1000000),(unsigned)((bps%1000000)/1000),
        (unsigned)(mib100/100),(unsigned)(mib100%100),utilization/100,utilization%100);
}
static void native_dma_handler(int nb_params,char **params)
{
    unsigned long address=MAIN_RAM_BASE+0x01000000,length=0x04000000,random=1,read_only=0;
    if((nb_params>0 && !parse_ulong(params[0],&address)) ||
       (nb_params>1 && !parse_ulong(params[1],&length)) ||
       (nb_params>2 && !parse_ulong(params[2],&random)) ||
       (nb_params>3 && !parse_ulong(params[3],&read_only))) {
        printf("DMA: invalid parameter\n");return;
    }
    if(address<MAIN_RAM_BASE || !length ||
        ((uint64_t)address+length)>((uint64_t)MAIN_RAM_BASE+MAIN_RAM_SIZE) ||
        ((address|length)&(dma_bench_data_width_read()/8-1)) || random>1 || read_only>1) {
        printf("DMA: require aligned nonempty region within DDR and boolean flags\n");return;
    }
    if(dma_bench_busy_read() || dma_bench_fault_read()>=3) {
        printf("DMA unavailable: busy or fatal fault; reconfigure FPGA after fatal fault\n");return;
    }
    if(!native_dma_admission_ready()) {
        printf("DMA refused: SDRAM calibration and memory test have not passed\n");return;
    }
    printf("Native DMA: mode=%s addr=%08lx bytes=%lu pattern=%s read_only=%lu width=%u fifo=%u clock=%u Hz\n",
        NATIVE_DMA_MODE_NAME,address,length,random ? "PRBS31" : "counter",read_only,
        (unsigned)dma_bench_data_width_read(),
        (unsigned)dma_bench_fifo_depth_read(), CONFIG_CLOCK_FREQUENCY);
    /* Prevent deferred CPU writes from modifying DMA data. */
    flush_cpu_dcache();flush_l2_cache();
    dma_bench_base_write(address-MAIN_RAM_BASE);dma_bench_length_write(length);
    dma_bench_random_write(random);dma_bench_read_only_write(read_only);
    dma_bench_timeout_write(NATIVE_DMA_HW_TIMEOUT_CYCLES);dma_bench_start_write(1);
    /* The DMA engine owns the primary cycle timeout. This outer deadline
     * catches missing completion reporting without depending on CPU speed. */
    struct timeout completion_timeout;
    timeout_start(&completion_timeout, native_dma_completion_timeout_us());
    while(!dma_bench_done_read() && !timeout_expired(&completion_timeout)) {}
    if(!dma_bench_done_read()) {
        printf("DMA completion timeout: reconfigure FPGA before further DDR use\n");
        return;
    }
    unsigned fault=dma_bench_fault_read(),errors=dma_bench_errors_read();
    unsigned writes=dma_bench_write_beats_read(),reads=dma_bench_read_beats_read();
    native_dma_rate("WRITE",writes,dma_bench_write_cycles_read());
    native_dma_rate("READ",reads,dma_bench_read_cycles_read());
    printf("DMA counters: write_cmd_stalls=%u read_cmd_stalls=%u errors=%u fault=%u first_error_offset=%08x\n",
        (unsigned)dma_bench_write_stalls_read(),
        (unsigned)dma_bench_read_stalls_read(), errors, fault,
        (unsigned)dma_bench_first_error_offset_read());
    unsigned expected=length/(dma_bench_data_width_read()/8);
    int pass=!fault && !errors && reads==expected && writes==(read_only?0:expected);
    printf("DMA_RESULT %s mode=%s addr=%08lx bytes=%lu pattern=%lu read_only=%lu\n",
        pass?"PASS":"FAIL",NATIVE_DMA_MODE_NAME,address,length,random,read_only);
    if(fault>=3) printf("DMA fatal fault: reconfigure FPGA before further DDR use\n");
}
define_command_args(native_dma,native_dma_handler,"Native-width DDR DMA throughput and integrity test (destructive)",
    "native_dma [address] [bytes] [PRBS31=1] [read_only=0]",0,4,MEM_CMDS);
