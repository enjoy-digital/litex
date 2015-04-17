/*
 * LitePCIe utilities
 *
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <inttypes.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>

#include "litepcie.h"
#include "cutils.h"
#include "config.h"
#include "csr.h"
#include "flags.h"
#include "litepcie_lib.h"

static inline uint32_t seed_to_data(uint32_t seed)
{
#if 1
    /* more random but slower */
    return seed * 0x31415976 + 1;
#else
    /* simplify debug: just copy the counter */
    return seed;
#endif
}

static void write_pn_data(uint32_t *dst, int count, uint32_t *pseed)
{
    int i;
    uint32_t seed;

    seed = *pseed;
    for(i = 0; i < count; i++) {
        dst[i] = seed_to_data(seed);
        seed++;
    }
    *pseed = seed;
}

/* Return the number of errors */
static int check_pn_data(const uint32_t *tab, int count,
                         uint32_t *pseed)
{
    int i, errors;
    uint32_t seed;

    errors = 0;
    seed = *pseed;
    for(i = 0; i < count; i++) {
        if (tab[i] != seed_to_data(seed)) {
            errors++;
        }
        seed++;
    }
    *pseed = seed;
    return errors;
}

#define MAX_SHIFT_OFFSET 128

/* test DMA with a buffer size of buf_size bytes in loopback
   mode. */
void dma_test(LitePCIeState *s, int buf_size, int buf_count, BOOL is_loopback)
{
    int is_first, tx_buf_num, buf_num_cur, buf_num_next;
    struct litepcie_ioctl_dma_wait dma_wait;
    int buf_stats_count; /* statistics */
    int64_t last_time;
    uint32_t tx_seed, rx_seed;
    int buf_rx_count, first_rx_buf, rx_errors, shift, d, tx_underflows;

    litepcie_dma_start(s, buf_size, buf_count, is_loopback);

    is_first = 1;
    buf_num_cur = 0; /* next buffer to receive */
    /* PN data TX and RX state */
    tx_seed = MAX_SHIFT_OFFSET;
    rx_seed = 0;
    buf_rx_count = 0;
    first_rx_buf = 1;

    /* statistics */
    buf_stats_count = 0;
    last_time = litepcie_get_time_ms();
    rx_errors = 0;
    shift = 0;
    tx_underflows = 0;

    for(;;) {
        /* wait until at least one buffer is received */
        dma_wait.timeout = 1000; /* 1 second timeout */
        dma_wait.tx_wait = FALSE;
        dma_wait.tx_buf_num = -1; /* not used */
        if (is_first) {
            dma_wait.rx_buf_num = -1; /* don't wait, just get the last
                                      received buffer number */
        } else {
            dma_wait.rx_buf_num = sub_mod_int(buf_num_cur, 1, buf_count);
        }
        /* wait until the current buffer number is different from
           dma_wait.buf_num */
        if (ioctl(s->litepcie_fd, LITEPCIE_IOCTL_DMA_WAIT, &dma_wait) < 0) {
            perror("LITEPCIE_IOCTL_DMA_WAIT");
        }
        if (is_first) {
            buf_num_cur = dma_wait.rx_buf_num;
            is_first = 0;
        }
        buf_num_next = add_mod_int(dma_wait.rx_buf_num, 1, buf_count);

        while (buf_num_cur != buf_num_next) {

            /* write the TX data 4/10 of a DMA cycle in the future */
            tx_buf_num = add_mod_int(buf_num_cur, 4*buf_count/10, buf_count);
            d = sub_mod_int(tx_buf_num, buf_num_next, buf_count);
            if (d >= (buf_count / 2)) {
                /* we are too late in writing data, which necessarily
                   gives read errors. */
                tx_underflows++;
            }

            write_pn_data((uint32_t *)(s->dma_tx_buf +
                                       tx_buf_num * s->dma_tx_buf_size),
                          s->tx_buf_size >> 2, &tx_seed);

            if (buf_rx_count >= 4*buf_count/10) {
                const uint32_t *rx_buf;
                int rx_buf_len;

                rx_buf = (uint32_t *)(s->dma_rx_buf + buf_num_cur * s->dma_rx_buf_size);
                rx_buf_len = s->rx_buf_size >> 2;

                if (first_rx_buf) {
                    uint32_t seed;

                    /* find the initial shift */
                    for(shift = 0; shift < 2 * MAX_SHIFT_OFFSET; shift++) {
                        seed = rx_seed + shift;
                        rx_errors = check_pn_data(rx_buf, rx_buf_len, &seed);
                        if (rx_errors <= (rx_buf_len / 2)) {
                            rx_seed = seed;
                            break;
                        }
                    }
                    if (shift == 2 * MAX_SHIFT_OFFSET) {
                        printf("Cannot find initial data\n");
                        exit(1);
                    } else {
                        printf("RX shift = %d\n",
                               -(shift - MAX_SHIFT_OFFSET));
                    }
                    first_rx_buf = 0;
                } else {
                    /* count the number of errors */
                    rx_errors += check_pn_data(rx_buf, rx_buf_len, &rx_seed);
                }
            } else {
                buf_rx_count++;
            }

            buf_num_cur = add_mod_int(buf_num_cur, 1, buf_count);

            /* statistics */
            if (++buf_stats_count == 10000) {
                int64_t duration;
                duration = litepcie_get_time_ms() - last_time;
                printf("%0.1f Gb/sec %0.1f bufs/sec tx_underflows=%d errors=%d\n",
                       (double)buf_stats_count * buf_size * 8 / ((double)duration * 1e6),
                       (double)buf_stats_count * 1000 / (double)duration,
                       tx_underflows, rx_errors);
                last_time = litepcie_get_time_ms();
                buf_stats_count = 0;
                tx_underflows = 0;
                rx_errors = 0;
            }
        }
    }

    litepcie_dma_stop(s);
}

void dma_loopback_test(void)
{
    LitePCIeState *s;

    s = litepcie_open(LITEPCIE_FILENAME);
    if (!s) {
        fprintf(stderr, "Could not init driver\n");
        exit(1);
    }
    dma_test(s, 16*1024, DMA_BUFFER_COUNT, TRUE);

    litepcie_close(s);
}

void dump_version(void)
{
    LitePCIeState *s;

    s = litepcie_open(LITEPCIE_FILENAME);
    if (!s) {
        fprintf(stderr, "Could not init driver\n");
        exit(1);
    }
    printf("sysid=0x%x\n", litepcie_readl(s, CSR_IDENTIFIER_SYSID_ADDR));
    printf("frequency=%d\n", litepcie_readl(s, CSR_IDENTIFIER_FREQUENCY_ADDR));

    litepcie_close(s);
}

void help(void)
{
    printf("usage: litepcie_util cmd [args...]\n"
           "\n"
           "available commands:\n"
           "dma_loopback_test                test DMA loopback operation\n"
           "version                          return fpga version\n"
           );
    exit(1);
}

int main(int argc, char **argv)
{
    const char *cmd;
    int c;

    for(;;) {
        c = getopt(argc, argv, "h");
        if (c == -1)
            break;
        switch(c) {
        case 'h':
            help();
            break;
        default:
            exit(1);
        }
    }

    if (optind >= argc)
        help();
    cmd = argv[optind++];

    if (!strcmp(cmd, "dma_loopback_test")) {
        dma_loopback_test();
    } else if (!strcmp(cmd, "version")) {
        dump_version();
    } else {
        help();
    }

    return 0;
}
