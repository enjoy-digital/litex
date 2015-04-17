/*
 * LitePCIe library
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
#include <errno.h>

#include "litepcie.h"
#include "cutils.h"
#include "config.h"
#include "csr.h"
#include "flags.h"

#include "litepcie_lib.h"

/*
  TODO:
  - DMA overflow/underflow detection
*/

void *litepcie_malloc(int size)
{
    return malloc(size);
}

void *litepcie_mallocz(int size)
{
    void *ptr;
    ptr = litepcie_malloc(size);
    if (!ptr)
        return NULL;
    memset(ptr, 0, size);
    return ptr;
}

void litepcie_free(void *ptr)
{
    free(ptr);
}

void __attribute__((format(printf, 2, 3))) litepcie_log(LitePCIeState *s, const char *fmt, ...)
{
    va_list ap;

    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
}

/* in ms */
int64_t litepcie_get_time_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000 + (ts.tv_nsec / 1000000U);
}

LitePCIeState *litepcie_open(const char *device_name)
{
    LitePCIeState *s;

    s = litepcie_mallocz(sizeof(LitePCIeState));
    if (!s)
        return NULL;

    s->litepcie_fd = open(device_name, O_RDWR);
    if (s->litepcie_fd < 0) {
        perror(device_name);
        goto fail;
    }

    /* map the DMA buffers */
    if (ioctl(s->litepcie_fd, LITEPCIE_IOCTL_GET_MMAP_INFO, &s->mmap_info) != 0) {
        perror("LITEPCIE_IOCTL_GET_MMAP_INFO");
        exit(1);
    }

    s->dma_tx_buf = mmap(NULL, s->mmap_info.dma_tx_buf_size *
                         s->mmap_info.dma_tx_buf_count,
                         PROT_READ | PROT_WRITE, MAP_SHARED, s->litepcie_fd,
                         s->mmap_info.dma_tx_buf_offset);
    if (s->dma_tx_buf == MAP_FAILED) {
        perror("mmap1");
        exit(1);
    }

    s->dma_rx_buf = mmap(NULL, s->mmap_info.dma_rx_buf_size *
                         s->mmap_info.dma_rx_buf_count,
                         PROT_READ | PROT_WRITE, MAP_SHARED, s->litepcie_fd,
                         s->mmap_info.dma_rx_buf_offset);
    if (s->dma_rx_buf == MAP_FAILED) {
        perror("mmap2");
        exit(1);
    }

    /* map the registers */
    s->reg_buf = mmap(NULL, s->mmap_info.reg_size,
                      PROT_READ | PROT_WRITE, MAP_SHARED, s->litepcie_fd,
                      s->mmap_info.reg_offset);
    if (s->reg_buf == MAP_FAILED) {
        perror("mmap2");
        exit(1);
    }

    s->dma_tx_buf_size = s->mmap_info.dma_tx_buf_size;
    s->dma_rx_buf_size = s->mmap_info.dma_rx_buf_size;

    pthread_mutex_init(&s->fifo_mutex, NULL);

    return s;
 fail:
    litepcie_close(s);
    return NULL;
}

void litepcie_dma_start(LitePCIeState *s, int buf_size, int buf_count, BOOL is_loopback)
{
    struct litepcie_ioctl_dma_start dma_start;

    if (buf_count > DMA_BUFFER_COUNT) {
        litepcie_log(s, "unsupported buf_count\n");
        exit(1);
    }

    s->tx_buf_size = s->rx_buf_size = buf_size;
    s->tx_buf_count = s->rx_buf_count = buf_count;

    dma_start.dma_flags = 0;
    if (is_loopback)
        dma_start.dma_flags |= DMA_LOOPBACK_ENABLE;
    dma_start.tx_buf_size = s->tx_buf_size;
    dma_start.tx_buf_count = s->tx_buf_count;
    dma_start.rx_buf_size = s->rx_buf_size;
    dma_start.rx_buf_count = s->rx_buf_count;
    if (ioctl(s->litepcie_fd, LITEPCIE_IOCTL_DMA_START, &dma_start) < 0) {
        perror("LITEPCIE_IOCTL_DMA_START");
    }
}

void litepcie_dma_stop(LitePCIeState *s)
{
    if (ioctl(s->litepcie_fd, LITEPCIE_IOCTL_DMA_STOP, NULL) < 0) {
        perror("LITEPCIE_IOCTL_DMA_STOP");
    }
}

void litepcie_writel(LitePCIeState *s, uint32_t addr, uint32_t val)
{
    *(volatile uint32_t *)(s->reg_buf + addr) = val;
}

uint32_t litepcie_readl(LitePCIeState *s, uint32_t addr)
{
    return *(volatile uint32_t *)(s->reg_buf + addr);
}

void litepcie_close(LitePCIeState *s)
{
    pthread_mutex_destroy(&s->fifo_mutex);

    if (s->dma_tx_buf) {
        munmap(s->dma_tx_buf, s->mmap_info.dma_tx_buf_size *
               s->mmap_info.dma_tx_buf_count);
    }
    if (s->dma_rx_buf) {
        munmap(s->dma_rx_buf, s->mmap_info.dma_rx_buf_size *
               s->mmap_info.dma_rx_buf_count);
    }
    if (s->reg_buf)
        munmap(s->reg_buf, s->mmap_info.reg_size);
    if (s->litepcie_fd >= 0)
        close(s->litepcie_fd);
    litepcie_free(s);
}
