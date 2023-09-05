// This file is Copyright (c) 2013 Werner Almesberger <werner@almesberger.net>
// This file is Copyright (c) 2013-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
// This file is Copyright (c) 2014-2022 Florent Kermarec <florent@enjoy-digital.fr>
// This file is Copyright (c) 2017 Greg Darke <greg@tsukasa.net.au>
// This file is Copyright (c) 2018 Ewen McNeill <ewen@naos.co.nz>

// License: BSD

#include <stdio.h>
#include <stdint.h>
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
static int last_ack; /* signed, so we can use -1 */
static uint16_t data_port;

static void rx_callback(uint32_t src_ip, uint16_t src_port,
    uint16_t dst_port, void *_data, unsigned int length)
{
	uint8_t *data = _data;
	uint16_t opcode;
	uint16_t block;
	int i;
	int offset;

	if(length < 4) return;
	if(dst_port != PORT_IN) return;
	opcode = data[0] << 8 | data[1];
	block = data[2] << 8 | data[3];
	if(opcode == TFTP_ACK) { /* Acknowledgement */
		data_port = src_port;
		last_ack = block;
		return;
	}
	if (opcode == TFTP_OACK) { /* Option Acknowledgement */
		packet_data = udp_get_tx_buffer();
		length = format_ack(packet_data, 0);
		udp_send(PORT_IN, src_port, length);
		return;
	}
	if(block < 1) return;
	if(opcode == TFTP_DATA) { /* Data */
		length -= 4;
		offset = (block-1)*BLOCK_SIZE;
		for(i=0;i<length;i++)
			dst_buffer[offset+i] = data[i+4];
		total_length += length;
		if(length < BLOCK_SIZE)
			transfer_finished = 1;

		packet_data = udp_get_tx_buffer();
		length = format_ack(packet_data, block);
		udp_send(PORT_IN, src_port, length);
	}
	if(opcode == TFTP_ERROR) { /* Error */
		total_length = -1;
		transfer_finished = 1;
	}
}

int tftp_get(uint32_t ip, uint16_t server_port, const char *filename,
    void *buffer)
{
	int len;
	int tries;
	int i;
	int length_before;

	if(!udp_arp_resolve(ip))
		return -1;

	udp_set_callback((udp_callback) rx_callback);

	dst_buffer = buffer;

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
	do {
		block++;
		send = sent+BLOCK_SIZE > size ? size-sent : BLOCK_SIZE;
		tries = 5;
		while(1) {
			packet_data = udp_get_tx_buffer();
			len = format_data(packet_data, block, buffer, send);
			udp_send(PORT_IN, data_port, len);
			for(i=0;i<12000000;i++) {
				udp_service();
				if(transfer_finished)
					goto fail;
				if(last_ack == block)
					goto next;
			}
			if (!--tries)
				goto fail;
		}
next:
		sent += send;
		buffer += send;
	} while (send == BLOCK_SIZE);

	udp_set_callback(NULL);

	return sent;

fail:
	udp_set_callback(NULL);
	return -1;
}
