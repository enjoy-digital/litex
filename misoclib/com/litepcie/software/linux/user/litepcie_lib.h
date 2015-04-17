/*
 * LitePCIe library
 *
 */
#ifndef LITEPCIE_LIB_H
#define LITEPCIE_LIB_H

#include <stdarg.h>
#include <pthread.h>

#define LITEPCIE_FILENAME "/dev/litepcie0"

typedef struct {
    int litepcie_fd;
    struct litepcie_ioctl_mmap_info mmap_info;
    uint8_t *dma_tx_buf;
    int dma_tx_buf_size;
    uint8_t *dma_rx_buf;
    int dma_rx_buf_size;
    uint8_t *reg_buf;

    unsigned int tx_buf_size; /* in bytes */
    unsigned int tx_buf_count; /* number of buffers */
    unsigned int rx_buf_size; /* in bytes */
    unsigned int rx_buf_count; /* number of buffers */

    unsigned int tx_buf_len; /* in samples */
    unsigned int rx_buf_len; /* in samples */

    pthread_mutex_t fifo_mutex;
    int64_t rx_timestamp; /* timestamp (in samples) of the current RX buffer */
    unsigned int rx_buf_index; /* index of the current RX buffer */
    unsigned int rx_buf_next; /* index of the next buffer after the
                                 last received buffer */
    BOOL has_rx_timestamp; /* true if received at least one buffer */

    int64_t tx_underflow_count; /* TX too late */
    int64_t rx_overflow_count; /* RX too late */
} LitePCIeState;

void *litepcie_malloc(int size);
void *litepcie_mallocz(int size);
void litepcie_free(void *ptr);
void __attribute__((format(printf, 2, 3))) litepcie_log(LitePCIeState *s, const char *fmt, ...);
int64_t litepcie_get_time_ms(void);
LitePCIeState *litepcie_open(const char *device_name);
void litepcie_close(LitePCIeState *s);
void litepcie_dma_start(LitePCIeState *s, int buf_size, int buf_count, BOOL is_loopback);
void litepcie_dma_stop(LitePCIeState *s);
void litepcie_writel(LitePCIeState *s, uint32_t addr, uint32_t val);
uint32_t litepcie_readl(LitePCIeState *s, uint32_t addr);

#endif /* LITEPCIE_LIB_H */
