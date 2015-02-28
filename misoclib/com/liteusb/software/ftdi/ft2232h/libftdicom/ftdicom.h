/*
 * ftdicom.c - Low Level USB communication interface
 *
 * Provides UART and DMA low level communication
 * functions for FT2232H in slave fifo mode.
 *
 * Copyright (C) 2014 florent@enjoy-digital.fr
 *
 */

#ifndef __FTDICOM_H
#define __FTDICOM_H

#include <stdint.h>
#include <stdbool.h>
#include <pthread.h>

#include "fastftdi.h"

/*
 * Protocol Constants
 */

#define UART_TAG 0
#define DMA_TAG 1

#define NEEDED_FOR_SIZE 9
#define PAYLOAD_OFFSET 10

#define INCOMPLETE -1
#define UNMATCHED 0


/*
 * Buffer Constants
 *
 * Buffer sizes must be a power of 2 so that modulos can be computed
 * with logical AND.
 */

// RAW
#define RAW_BUFFER_SIZE 20*1024*1024

// UART
#define UART_RINGBUFFER_SIZE_RX 4096
#define UART_RINGBUFFER_MASK_RX (UART_RINGBUFFER_SIZE_RX-1)

// DMA
#define DMA_BUFFER_SIZE_TX 20*1024*1024
#define DMA_BUFFER_SIZE_RX 20*1024*1024


/*
 * Struct
 */
typedef int (*dma_read_ext_callback_t)(uint8_t *buffer, int length, void *userdata);
typedef struct {
	FTDIDevice *dev;

	uint8_t *raw_tx_buf;
	uint8_t *raw_rx_buf;
	unsigned int raw_rx_buf_length;

	char *uart_rx_buf;
	volatile unsigned int uart_rx_produce;
	volatile unsigned int uart_rx_consume;

	pthread_t *thread;
	dma_read_ext_callback_t dma_read_ext_callback;

	void *userdata;
} FTDICom;

/*
 * Public Functions
 */

int ftdicom_open(FTDICom *com);
void ftdicom_close(FTDICom *com);

int ftdicom_uart_write_buffer(FTDICom *com, uint8_t *data, size_t length);
int ftdicom_uart_write(FTDICom *com, uint8_t c);
uint8_t ftdicom_uart_read(FTDICom *com);
int ftdicom_uart_read_nonblock(FTDICom *com);

int ftdicom_dma_write(FTDICom *com, uint8_t *data, size_t length);
void ftdicom_dma_read_set_callback(FTDICom *com, dma_read_ext_callback_t callback, void *userdata);

/*
 * Private Functions
 */
int ftdicom_write(FTDICom *com, uint8_t tag, uint8_t *data, size_t length, uint8_t with_crc);

int ftdicom_present_bytes(uint8_t tag, uint8_t *buffer, int length);
int ftdicom_uart_present_bytes(uint8_t *buffer, int length);
int ftdicom_dma_present_bytes(uint8_t *buffer, int length);
int ftdicom_read_callback(uint8_t *buffer, int length, FTDIProgressInfo *progress, void *userdata);
void *ftdicom_read_thread(void *userdata);

void ftdicom_uart_read_callback(FTDICom *com, uint8_t *buffer, int length);
int ftdicom_dma_read_callback(FTDICom *com, uint8_t *buffer, int length);


#endif /* __FTDICOM_H */
