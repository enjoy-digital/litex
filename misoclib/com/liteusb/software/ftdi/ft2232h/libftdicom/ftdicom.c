/*
 * ftdicom.c - Low Level USB communication interface
 *
 * Provides UART and DMA low level communication
 * functions for FT2232H in slave fifo mode.
 *
 * Copyright (C) 2014 florent@enjoy-digital.fr
 *
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdbool.h>
#include "ftdicom.h"
#include "crc.h"

/*
 * Open / close functions
 */
int ftdicom_open(FTDICom *com)
{
	int err = 0;
	err =  FTDIDevice_Open(com->dev);
	if (err)
		return err;

	com->raw_tx_buf = malloc(RAW_BUFFER_SIZE);
	com->raw_rx_buf = malloc(RAW_BUFFER_SIZE);
	com->uart_rx_buf = malloc(UART_RINGBUFFER_SIZE_RX);

	err = FTDIDevice_SetMode(com->dev, FTDI_INTERFACE_A, FTDI_BITMODE_SYNC_FIFO, 0xFF, 0);
	if (err)
		return err;

	com->raw_rx_buf_length = 0;

	pthread_t thread;
	com->thread = &thread;
	pthread_create(com->thread, NULL, ftdicom_read_thread, com);

	return 0;
}

void ftdicom_close(FTDICom *com)
{
	free(com->raw_tx_buf);
	free(com->raw_rx_buf);
	free(com->uart_rx_buf);
	FTDIDevice_Close(com->dev);
	free(com->thread);
}

/*
 * Write (Tx) functions
 */
int ftdicom_write(FTDICom *com, uint8_t tag, uint8_t *data, size_t length, uint8_t with_crc)
{
	unsigned int computed_crc;

	com->raw_tx_buf[0] = 0x5A;
	com->raw_tx_buf[1] = 0xA5;
	com->raw_tx_buf[2] = 0x5A;
	com->raw_tx_buf[3] = 0xA5;
	com->raw_tx_buf[4] = tag;
	if (with_crc)
		length += 4;
	com->raw_tx_buf[5] = (length >> 24) & 0xff;
	com->raw_tx_buf[6] = (length >> 16) & 0xff;
	com->raw_tx_buf[7] = (length >>  8) & 0xff;
	com->raw_tx_buf[8] = (length >>  0) & 0xff;

	memcpy(com->raw_tx_buf+9, data, length);
	if (with_crc) {
		computed_crc = crc32(data, length-4);
		com->raw_tx_buf[9+length-1] = (computed_crc >> 24) & 0xff;
		com->raw_tx_buf[9+length-2] = (computed_crc >> 16) & 0xff;
		com->raw_tx_buf[9+length-3] = (computed_crc >> 8) & 0xff;
		com->raw_tx_buf[9+length-4] = (computed_crc >> 0) & 0xff;
	}
	return FTDIDevice_Write(com->dev, FTDI_INTERFACE_A, com->raw_tx_buf, 9+length, false);
}

/*
 * Read (Rx) common functions
 */

int ftdicom_present_bytes(uint8_t tag, uint8_t *buffer, int length)
{
	if (length < NEEDED_FOR_SIZE)
		return INCOMPLETE;

	if (buffer[0] != 0x5A ||
		buffer[1] != 0xA5 ||
		buffer[2] != 0x5A ||
		buffer[3] != 0xA5 ||
		buffer[4] != tag)
		return UNMATCHED;

	int size = NEEDED_FOR_SIZE;
	size += buffer[5] << 24;
	size += buffer[6] << 16;
	size += buffer[7] << 8;
	size += buffer[8];

	if (length < size)
		return INCOMPLETE;

	return size;
}

int ftdicom_uart_present_bytes(uint8_t *buffer, int length)
{
	return ftdicom_present_bytes(UART_TAG, buffer, length);
}

int ftdicom_dma_present_bytes(uint8_t *buffer, int length)
{
	return ftdicom_present_bytes(DMA_TAG, buffer, length);
}

int ftdicom_read_callback(uint8_t *buffer, int length, FTDIProgressInfo *progress, void *userdata)
{
	FTDICom *com = (FTDICom *) userdata;

	// Concatenate buffer & raw_rx_buf
	memcpy(com->raw_rx_buf + com->raw_rx_buf_length, buffer, length);
	com->raw_rx_buf_length += length;

	int code = 0;
	int incomplete = 0;
	int i = 0;

	// Search frames in raw_rx_buf
	while (i != com->raw_rx_buf_length && !incomplete)
	{
		code = 0;

		// UART
		code = ftdicom_uart_present_bytes(com->raw_rx_buf + i, com->raw_rx_buf_length-i);
		if (code == INCOMPLETE)
		{
			incomplete = 1;
			break;
		} else if (code)
		{
			ftdicom_uart_read_callback(com, com->raw_rx_buf + i + NEEDED_FOR_SIZE, code-NEEDED_FOR_SIZE);
			i += code-1;
		}

		// DMA
		code = ftdicom_dma_present_bytes(com->raw_rx_buf + i, com->raw_rx_buf_length-i);
		if (code == INCOMPLETE)
		{
			incomplete = 1;
			break;
		} else if (code)
		{
			ftdicom_dma_read_callback(com, com->raw_rx_buf + i + NEEDED_FOR_SIZE, code-NEEDED_FOR_SIZE);
			i += code;
		}

		// Nothing found, increment index
		if (code == UNMATCHED)
			i=i+1;

	}

	// Prepare raw_rx_buf for next callback
	if (incomplete == 1)
	{
		com->raw_rx_buf_length = com->raw_rx_buf_length - i;
		memcpy(com->raw_rx_buf, com->raw_rx_buf + i, com->raw_rx_buf_length);
	} else {
		com->raw_rx_buf_length = 0;
	}

	return 0;
}

void *ftdicom_read_thread(void *userdata)
{
	FTDICom *com = (FTDICom *) userdata;
	FTDIDevice_ReadStream(com->dev, FTDI_INTERFACE_A, ftdicom_read_callback, com, 8, 16);
	return 0;
}

/*
 * UART functions
 */

int ftdicom_uart_write_buffer(FTDICom *com, uint8_t *data, size_t length)
{
	return ftdicom_write(com, UART_TAG, data, length, 0);
}

int ftdicom_uart_write(FTDICom *com, uint8_t c)
{
	return ftdicom_write(com, UART_TAG, &c, 1, 0);
}

void ftdicom_uart_read_callback(FTDICom *com, uint8_t *buffer, int length)
{
	while (length > 0) {
		com->uart_rx_buf[com->uart_rx_produce] = buffer[0];
		com->uart_rx_produce = (com->uart_rx_produce + 1) & UART_RINGBUFFER_MASK_RX;
		length -=1;
		buffer +=1;
	}
}

uint8_t ftdicom_uart_read(FTDICom *com)
{
	uint8_t c;

	while(com->uart_rx_consume == com->uart_rx_produce);
	c = com->uart_rx_buf[com->uart_rx_consume];
	com->uart_rx_consume = (com->uart_rx_consume + 1) & UART_RINGBUFFER_MASK_RX;
	return c;
}

int ftdicom_uart_read_nonblock(FTDICom *com)
{
	return (com->uart_rx_consume != com->uart_rx_produce);
}

/*
 * DMA functions
 */
int ftdicom_dma_write(FTDICom *com, uint8_t *data, size_t length)
{
	return ftdicom_write(com, DMA_TAG, data, length, 1);
}

void ftdicom_dma_read_set_callback(FTDICom *com, dma_read_ext_callback_t callback, void *userdata)
{
	com->dma_read_ext_callback = callback;
	com->userdata = userdata;
}

int ftdicom_dma_read_callback(FTDICom *com, uint8_t *buffer, int length)
{
	unsigned int received_crc;
	unsigned int computed_crc;

	received_crc = ((unsigned int)buffer[length-1] << 24)
		|((unsigned int)buffer[length-2] << 16)
		|((unsigned int)buffer[length-3] <<  8)
		|((unsigned int)buffer[length-4]);
	computed_crc = crc32(buffer, length-4);
	if(received_crc != computed_crc) return -1;

	if (com->dma_read_ext_callback != NULL)
		return com->dma_read_ext_callback(buffer, length-4, com->userdata);
	else
		return -1;
}