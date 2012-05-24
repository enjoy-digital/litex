#ifndef __SFL_H
#define __SFL_H

#define SFL_MAGIC_LEN 14
#define SFL_MAGIC_REQ "sL5DdSMmkekro\n"
#define SFL_MAGIC_ACK "z6IHG7cYDID6o\n"

struct sfl_frame {
	unsigned char length;
	unsigned char crc[2];
	unsigned char cmd;
	unsigned char payload[255];
} __attribute__((packed));

/* General commands */
#define SFL_CMD_ABORT		0x00
#define SFL_CMD_LOAD		0x01
#define SFL_CMD_JUMP		0x02

/* Linux-specific commands */
#define SFL_CMD_CMDLINE		0x03
#define SFL_CMD_INITRDSTART	0x04
#define SFL_CMD_INITRDEND	0x05

/* Replies */
#define SFL_ACK_SUCCESS		'K'
#define SFL_ACK_CRCERROR	'C'
#define SFL_ACK_UNKNOWN		'U'
#define SFL_ACK_ERROR		'E'

#endif /* __SFL_H */
