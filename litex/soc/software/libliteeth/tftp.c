// This file is Copyright (c) 2013 Werner Almesberger <werner@almesberger.net>
// This file is Copyright (c) 2013-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
// This file is Copyright (c) 2014-2022 Florent Kermarec <florent@enjoy-digital.fr>
// This file is Copyright (c) 2017 Greg Darke <greg@tsukasa.net.au>
// This file is Copyright (c) 2018 Ewen McNeill <ewen@naos.co.nz>

// License: BSD

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <stddef.h>
#include <limits.h>
#include <string.h>

#include <libbase/progress.h>

#include <libliteeth/udp.h>
#include <libliteeth/tftp.h>

/* Local TFTP client port (arbitrary) */
#define PORT_IN		7642

enum {
	TFTP_RRQ	= 1,	/* Read request */
	TFTP_WRQ	= 2, 	/* Write request */
	TFTP_DATA	= 3,	/* Data */
	TFTP_ACK	= 4,	/* Acknowledgment */
	TFTP_ERROR	= 5,	/* Error */
	TFTP_OACK	= 6,	/* Option Acknowledgment */
};

#define	BLOCK_SIZE	1024 /* block size in bytes 512 or 1024*/

static int format_request(uint8_t *buf, uint16_t op, const char *filename)
{
	int len = strlen(filename);

	*buf++ = op >> 8; /* Opcode */
	*buf++ = op;
	memcpy(buf, filename, len);
	buf += len;
	*buf++ = 0x00;
	*buf++ = 'o';
	*buf++ = 'c';
	*buf++ = 't';
	*buf++ = 'e';
	*buf++ = 't';
	*buf++ = 0x00;
#if (BLOCK_SIZE == 1024)
	*buf++ = 'b';
	*buf++ = 'l';
	*buf++ = 'k';
	*buf++ = 's';
	*buf++ = 'i';
	*buf++ = 'z';
	*buf++ = 'e';
	*buf++ = 0x00;
	*buf++ = '1';
	*buf++ = '0';
	*buf++ = '2';
	*buf++ = '4';
	*buf++ = 0x00;
	return 9 + 13 + strlen(filename);
#else
	return 9 + strlen(filename);
#endif
}

static int format_ack(uint8_t *buf, uint16_t block)
{
	*buf++ = 0x00; /* Opcode: Ack */
	*buf++ = TFTP_ACK;
	*buf++ = (block & 0xff00) >> 8;
	*buf++ = (block & 0x00ff);
	return 4;
}

static int format_data(uint8_t *buf, uint16_t block, const void *data, int len)
{
	*buf++ = 0x00; /* Opcode: Data*/
	*buf++ = TFTP_DATA;
	*buf++ = (block & 0xff00) >> 8;
	*buf++ = (block & 0x00ff);
	memcpy(buf, data, len);
	return len+4;
}

static uint8_t *packet_data;
static int total_length;
static int transfer_finished;
static uint8_t *dst_buffer;
static size_t dst_buffer_size;
static int last_ack; /* signed, so we can use -1 */
static uint32_t server_ip;
static uint16_t data_port;
static uint16_t next_data_block;
static size_t current_offset;
static size_t block_size; /* negotiated block size, 0 while unknown */
static int tftp_write;

static int check_server(uint32_t src_ip, uint16_t src_port)
{
	if(src_ip != server_ip) return 0;
	if(data_port && (src_port != data_port)) return 0;
	if(!data_port) data_port = src_port;
	return 1;
}

static void send_ack(uint16_t block)
{
	packet_data = udp_get_tx_buffer();
	udp_send(PORT_IN, data_port, format_ack(packet_data, block));
}

static void rx_callback(uint32_t src_ip, uint16_t src_port,
    uint16_t dst_port, void *_data, unsigned int length)
{
	uint8_t *data = _data;
	uint16_t opcode;
	uint16_t block;
	size_t i;
	size_t offset;

	if(length < 4) return;
	if(dst_port != PORT_IN) return;
	opcode = data[0] << 8 | data[1];
	block = data[2] << 8 | data[3];
	if(opcode == TFTP_ACK) { /* Acknowledgement */
		if(!tftp_write) return;
		if(!check_server(src_ip, src_port)) return;
		last_ack = block;
		return;
	}
	if (opcode == TFTP_OACK) { /* Option Acknowledgement */
		size_t pos;
		size_t start;
		const char *name = NULL;

		if(!check_server(src_ip, src_port)) return;
		/* RFC 2348: the server may grant a smaller block size than the one
		   requested or omit the option entirely (512-byte default). Parse
		   the granted value instead of assuming our request was honored.
		   The payload is a sequence of NUL-terminated name/value strings. */
		block_size = 512;
		start = 2;
		for(pos = 2; pos < length; pos++) {
			if(data[pos] != 0)
				continue;
			if(name == NULL) {
				name = (const char *)&data[start];
			} else {
				if(strcmp(name, "blksize") == 0) {
					unsigned long value = strtoul((const char *)&data[start], NULL, 10);
					if((value >= 8) && (value <= BLOCK_SIZE))
						block_size = value;
				}
				name = NULL;
			}
			start = pos + 1;
		}
		if(!tftp_write)
			send_ack(0);
		last_ack = 0;
		return;
	}
	if(opcode == TFTP_ERROR) { /* Error */
		if(!check_server(src_ip, src_port)) return;
		/* For ERROR packets, bytes 2-3 are the error code and a NetASCII
		   message follows; report them instead of failing silently. */
		if(length > 4)
			printf("TFTP error %d: %.*s\n", block, (int)(length - 4), (char *)&data[4]);
		else
			printf("TFTP error %d\n", block);
		total_length = -1;
		transfer_finished = 1;
		return;
	}
	if(opcode == TFTP_DATA) { /* Data */
		if(tftp_write) return;
		if(!check_server(src_ip, src_port)) return;
		/* No OACK seen: server without option support, RFC default size. */
		if(block_size == 0)
			block_size = 512;
		length -= 4;
		/* Block numbers are 16-bit and wrap on transfers > 64MB, so compare
		   them modulo 2^16 and track the write offset separately. */
		if(block == (uint16_t)(next_data_block - 1)) {
			/* Duplicate of the previous block: re-acknowledge (only when a block has
			   actually been received; a spurious block 0 at transfer start is dropped). */
			if((current_offset != 0) || (next_data_block != 1))
				send_ack(block);
			return;
		}
		if(block != next_data_block)
			return;
		if ((length > dst_buffer_size) || (current_offset > (dst_buffer_size - length))) {
			total_length = -1;
			transfer_finished = 1;
			return;
		}
		if((current_offset + length) > INT_MAX) {
			total_length = -1;
			transfer_finished = 1;
			return;
		}

		offset = current_offset;
		for(i=0;i<length;i++)
			dst_buffer[offset+i] = data[i+4];
		current_offset += length;
		total_length = current_offset;
		next_data_block++;
		if(length < block_size)
			transfer_finished = 1;

		send_ack(block);
	}
}

int tftp_get(uint32_t ip, uint16_t server_port, const char *filename,
    void *buffer, size_t max_size)
{
	int len;
	int tries;
	int i;
	int length_before;

	if(!udp_arp_resolve(ip)) {
		printf("ARP failed\n");
		return -1;
	}

	server_ip = ip;
	data_port = 0;
	next_data_block = 1;
	current_offset = 0;
	block_size = 0;
	last_ack = -1;
	tftp_write = 0;

	udp_set_callback((udp_callback) rx_callback);

	dst_buffer = buffer;
	dst_buffer_size = max_size;

	total_length = 0;
	transfer_finished = 0;
	tries = 5;
	while(1) {
		packet_data = udp_get_tx_buffer();
		len = format_request(packet_data, TFTP_RRQ, filename);
		udp_send(PORT_IN, server_port, len);
		for(i=0;i<2000000;i++) {
			udp_service();
			if((total_length > 0) || transfer_finished) break;
		}
		if((total_length > 0) || transfer_finished) break;
		tries--;
		if(tries == 0) {
			udp_set_callback(NULL);
			return -1;
		}
	}

	i = 12000000;
	length_before = total_length;
	init_progression_bar(0);
	while(!transfer_finished) {
		if(length_before != total_length) {
			i = 12000000;
			length_before = total_length;
			/* TFTP does not know the file size up front: print one '#' per
			   downloaded MB, plus a spinner for intra-MB activity. */
			show_progress(total_length >> 20);
			if ((total_length & (0x8000 - 1)) == 0)
				show_progress(-1);
		}
		if(i-- == 0) {
			udp_set_callback(NULL);
			return -1;
		}
		udp_service();
	}

	udp_set_callback(NULL);

	return total_length;
}

int tftp_put(uint32_t ip, uint16_t server_port, const char *filename,
    const void *buffer, int size)
{
	int len, send;
	int tries;
	int i;
	int block = 0, sent = 0;

	if(!udp_arp_resolve(ip))
		return -1;

	server_ip = ip;
	data_port = 0;
	next_data_block = 1;
	current_offset = 0;
	block_size = 0;
	last_ack = -1;
	tftp_write = 1;

	udp_set_callback((udp_callback) rx_callback);

	packet_data = udp_get_tx_buffer();

	total_length = 0;
	transfer_finished = 0;
	tries = 5;
	while(1) {
		packet_data = udp_get_tx_buffer();
		len = format_request(packet_data, TFTP_WRQ, filename);
		udp_send(PORT_IN, server_port, len);
		for(i=0;i<2000000;i++) {
			last_ack = -1;
			udp_service();
			if(last_ack == block)
				goto send_data;
			if(transfer_finished)
				goto fail;
		}
		tries--;
		if(tries == 0)
			goto fail;
	}

send_data:
	/* A plain ACK 0 (no OACK) means the server does not support options
	   and expects the RFC default block size. */
	if(block_size == 0)
		block_size = 512;
	do {
		block++;
		send = sent+block_size > size ? size-sent : block_size;
		tries = 5;
		while(1) {
			packet_data = udp_get_tx_buffer();
			len = format_data(packet_data, block, buffer, send);
			udp_send(PORT_IN, data_port, len);
			for(i=0;i<12000000;i++) {
				udp_service();
				if(transfer_finished)
					goto fail;
				/* Block numbers wrap modulo 2^16 on transfers > 64MB. */
				if(last_ack == (uint16_t)block)
					goto next;
			}
			if (!--tries)
				goto fail;
		}
next:
		sent += send;
		buffer += send;
	} while (send == block_size);

	udp_set_callback(NULL);

	return sent;

fail:
	udp_set_callback(NULL);
	return -1;
}
