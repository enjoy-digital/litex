/*
 * LitePCIe driver
 *
 */
#ifndef _LINUX_LITEPCIE_H
#define _LINUX_LITEPCIE_H

#include <linux/types.h>

struct litepcie_ioctl_mmap_info {
    unsigned long reg_offset;
    unsigned long reg_size;

    unsigned long dma_tx_buf_offset;
    unsigned long dma_tx_buf_size;
    unsigned long dma_tx_buf_count;

    unsigned long dma_rx_buf_offset;
    unsigned long dma_rx_buf_size;
    unsigned long dma_rx_buf_count;
};

struct litepcie_ioctl_dma_start {
    __u32 dma_flags; /* see LITEPCIE_DMA_FLAGS_x */
    __u32 tx_buf_size; /* in bytes, must be < dma_buf_pitch. 0 means no TX */
    __u32 tx_buf_count;
    __u32 rx_buf_size; /* in bytes, must be < dma_buf_pitch. 0 means no RX */
    __u32 rx_buf_count;
};

/* if tx_wait is true, wait until the current TX bufffer is
   different from tx_buf_num. If tx_wait is false, wait until the
   current RX buffer is different from rx_buf_num. Return the last
   TX buffer in tx_buf_num and the last RX buffer in
   rx_buf_num. */
struct litepcie_ioctl_dma_wait {
    __s32 timeout; /* in ms. Return -EAGAIN if timeout occured without event */
    __u32 tx_wait;
    __u32 tx_buf_num; /* read/write */
    __u32 rx_buf_num; /* read/write */
};

#define LITEPCIE_IOCTL 'S'

#define LITEPCIE_IOCTL_GET_MMAP_INFO _IOR(LITEPCIE_IOCTL, 0, struct litepcie_ioctl_mmap_info)
#define LITEPCIE_IOCTL_DMA_START _IOW(LITEPCIE_IOCTL, 1, struct litepcie_ioctl_dma_start)
#define LITEPCIE_IOCTL_DMA_STOP  _IO(LITEPCIE_IOCTL, 2)
#define LITEPCIE_IOCTL_DMA_WAIT  _IOWR(LITEPCIE_IOCTL, 3, struct litepcie_ioctl_dma_wait)

#endif /* _LINUX_LITEPCIE_H */
