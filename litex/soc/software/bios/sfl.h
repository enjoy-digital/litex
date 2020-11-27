// This file is Copyright (c) 2012-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
// License: BSD

#ifndef __SFL_H
#define __SFL_H

#define SFL_MAGIC_LEN 14
#define SFL_MAGIC_REQ "sL5DdSMmkekro\n"
#define SFL_MAGIC_ACK "z6IHG7cYDID6o\n"

struct sfl_frame {
	unsigned char payload_length;
	unsigned char crc[2];
	unsigned char cmd;
	unsigned char payload[255];
} __attribute__((packed));

#define SFL_VERSION 2

/* General commands */
#define SFL_CMD_ABORT		0x00
#define SFL_CMD_LOAD		0x01
#define SFL_CMD_JUMP		0x02
#define SFL_CMD_LOAD_NO_CRC	0x03
#define SFL_CMD_FLASH		0x04
#define SFL_CMD_REBOOT		0x05
/* Commands available from version 2 */
#define SFL_CMD_VERSION		0x06
#define SFL_CMD_LOAD_ASYNC	0x07
#define SFL_CMD_RESYNC		0x08

#define SFL_MAX_CMD         SFL_CMD_RESYNC

/* Replies */
#define SFL_ACK_SUCCESS		'K'
#define SFL_ACK_CRCERROR	'C'
#define SFL_ACK_UNKNOWN		'U'
#define SFL_ACK_ERROR		'E'
/* Followed by a 1 byte version number if the protocol version is at least 2.
 * Otherwise SFL_ACK_UNKNOWN will be returned instead. */
#define SFL_ACK_VERSION		'V'
/* Followed by a 4 byte big endian address that needs to be resent via
 * LOAD_ASYNC. */
#define SFL_ACK_RESEND		'R'
/* Followed by a 4 byte big endian address that was successfully loaded via
 * LOAD_ASYNC. */
#define SFL_ACK_ASYNC		'A'

#endif /* __SFL_H */
