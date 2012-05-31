#include <stdio.h>
#include <console.h>
#include <uart.h>
#include <system.h>
#include <board.h>
#include <crc.h>
#include <sfl.h>
#include <string.h>
#include <irq.h>
#include <timer.h>

#include <hw/mem.h>

#include "microudp.h"
#include "tftp.h"
#include "boot.h"

extern int rescue;
extern void boot_helper(unsigned int r1, unsigned int r2, unsigned int r3, unsigned int r4, unsigned int addr);

static void __attribute__((noreturn)) boot(unsigned int r1, unsigned int r2, unsigned int r3, unsigned int r4, unsigned int addr)
{
	printf("Executing booted program.\n");
	uart_sync();
	irq_setmask(0);
	irq_setie(0);
	boot_helper(r1, r2, r3, r4, addr);
	while(1);
}

static int check_ack(void)
{
	int recognized;
	static const char str[SFL_MAGIC_LEN] = SFL_MAGIC_ACK;

	timer_enable(0);
	timer_set_reload(0);
	timer_set_counter(get_system_frequency()/4);
	timer_enable(1);
	recognized = 0;
	while(timer_get()) {
		if(uart_read_nonblock()) {
			char c;
			c = uart_read();
			if(c == str[recognized]) {
				recognized++;
				if(recognized == SFL_MAGIC_LEN)
					return 1;
			} else {
				if(c == str[0])
					recognized = 1;
				else
					recognized = 0;
			}
		}
	}
	return 0;
}

#define MAX_FAILED 5

void serialboot(void)
{
	struct sfl_frame frame;
	int failed;
	unsigned int cmdline_adr, initrdstart_adr, initrdend_adr;
	static const char str[SFL_MAGIC_LEN+1] = SFL_MAGIC_REQ;
	const char *c;

	printf("Booting from serial...\n");

	c = str;
	while(*c) {
		uart_write(*c);
		c++;
	}
	if(!check_ack()) {
		printf("Timeout\n");
		return;
	}

	failed = 0;
	cmdline_adr = initrdstart_adr = initrdend_adr = 0;
	while(1) {
		int i;
		int actualcrc;
		int goodcrc;

		/* Grab one frame */
		frame.length = uart_read();
		frame.crc[0] = uart_read();
		frame.crc[1] = uart_read();
		frame.cmd = uart_read();
		for(i=0;i<frame.length;i++)
			frame.payload[i] = uart_read();

		/* Check CRC */
		actualcrc = ((int)frame.crc[0] << 8)|(int)frame.crc[1];
		goodcrc = crc16(&frame.cmd, frame.length+1);
		if(actualcrc != goodcrc) {
			failed++;
			if(failed == MAX_FAILED) {
				printf("Too many consecutive errors, aborting");
				return;
			}
			uart_write(SFL_ACK_CRCERROR);
			continue;
		}

		/* CRC OK */
		switch(frame.cmd) {
			case SFL_CMD_ABORT:
				failed = 0;
				uart_write(SFL_ACK_SUCCESS);
				return;
			case SFL_CMD_LOAD: {
				char *writepointer;

				failed = 0;
				writepointer = (char *)(
					 ((unsigned int)frame.payload[0] << 24)
					|((unsigned int)frame.payload[1] << 16)
					|((unsigned int)frame.payload[2] << 8)
					|((unsigned int)frame.payload[3] << 0));
				for(i=4;i<frame.length;i++)
					*(writepointer++) = frame.payload[i];
				uart_write(SFL_ACK_SUCCESS);
				break;
			}
			case SFL_CMD_JUMP: {
				unsigned int addr;

				failed = 0;
				addr =  ((unsigned int)frame.payload[0] << 24)
					|((unsigned int)frame.payload[1] << 16)
					|((unsigned int)frame.payload[2] << 8)
					|((unsigned int)frame.payload[3] << 0);
				uart_write(SFL_ACK_SUCCESS);
				boot(cmdline_adr, initrdstart_adr, initrdend_adr, rescue, addr);
				break;
			}
			case SFL_CMD_CMDLINE:
				failed = 0;
				cmdline_adr =  ((unsigned int)frame.payload[0] << 24)
					      |((unsigned int)frame.payload[1] << 16)
					      |((unsigned int)frame.payload[2] << 8)
					      |((unsigned int)frame.payload[3] << 0);
				uart_write(SFL_ACK_SUCCESS);
				break;
			case SFL_CMD_INITRDSTART:
				failed = 0;
				initrdstart_adr =  ((unsigned int)frame.payload[0] << 24)
					          |((unsigned int)frame.payload[1] << 16)
					          |((unsigned int)frame.payload[2] << 8)
					          |((unsigned int)frame.payload[3] << 0);
				uart_write(SFL_ACK_SUCCESS);
				break;
			case SFL_CMD_INITRDEND:
				failed = 0;
				initrdend_adr =  ((unsigned int)frame.payload[0] << 24)
					        |((unsigned int)frame.payload[1] << 16)
					        |((unsigned int)frame.payload[2] << 8)
					        |((unsigned int)frame.payload[3] << 0);
				uart_write(SFL_ACK_SUCCESS);
				break;
			default:
				failed++;
				if(failed == MAX_FAILED) {
					printf("Too many consecutive errors, aborting");
					return;
				}
				uart_write(SFL_ACK_UNKNOWN);
				break;
		}
	}
}

#define LOCALIP1 192
#define LOCALIP2 168
#define LOCALIP3 0
#define LOCALIP4 42
#define REMOTEIP1 192
#define REMOTEIP2 168
#define REMOTEIP3 0
#define REMOTEIP4 14

static int tftp_get_v(unsigned int ip, const char *filename, char *buffer)
{
	int r;

	r = tftp_get(ip, filename, buffer);
	if(r > 0)
		printf("Successfully downloaded %d bytes from %s over TFTP\n", r, filename);
	else
		printf("Unable to download %s over TFTP\n", filename);
	return r;
}

void netboot(void)
{
	int size;
	unsigned int cmdline_adr, initrdstart_adr, initrdend_adr;
	unsigned int ip;
	unsigned char *macadr = (unsigned char *)FLASH_OFFSET_MAC_ADDRESS;

	printf("Booting from network...\n");
	printf("Local IP : %d.%d.%d.%d\n", LOCALIP1, LOCALIP2, LOCALIP3, LOCALIP4);
	printf("Remote IP: %d.%d.%d.%d\n", REMOTEIP1, REMOTEIP2, REMOTEIP3, REMOTEIP4);

	ip = IPTOINT(REMOTEIP1, REMOTEIP2, REMOTEIP3, REMOTEIP4);

	microudp_start(macadr, IPTOINT(LOCALIP1, LOCALIP2, LOCALIP3, LOCALIP4));

	if(tftp_get_v(ip, "boot.bin", (void *)SDRAM_BASE) <= 0) {
		printf("Network boot failed\n");
		return;
	}

	cmdline_adr = SDRAM_BASE+0x1000000;
	size = tftp_get_v(ip, "cmdline.txt", (void *)cmdline_adr);
	if(size <= 0) {
		printf("No command line parameters found\n");
		cmdline_adr = 0;
	} else
		*((char *)(cmdline_adr+size)) = 0x00;

	initrdstart_adr = SDRAM_BASE+0x1002000;
	size = tftp_get_v(ip, "initrd.bin", (void *)initrdstart_adr);
	if(size <= 0) {
		printf("No initial ramdisk found\n");
		initrdstart_adr = 0;
		initrdend_adr = 0;
	} else
		initrdend_adr = initrdstart_adr + size;

	boot(cmdline_adr, initrdstart_adr, initrdend_adr, rescue, SDRAM_BASE);
}

void flashboot(void)
{
	unsigned int *flashbase;
	unsigned int length;
	unsigned int crc;
	unsigned int got_crc;

	printf("Booting from flash...\n");
	if(rescue)
		flashbase = (unsigned int *)FLASH_OFFSET_RESCUE_APP;
	else
		flashbase = (unsigned int *)FLASH_OFFSET_REGULAR_APP;
	length = *flashbase++;
	crc = *flashbase++;
	if((length < 32) || (length > 4*1024*1024)) {
		printf("Error: Invalid flash boot image length\n");
		return;
	}
	
	printf("Loading %d bytes from flash...\n", length);
	memcpy((void *)SDRAM_BASE, flashbase, length);
	got_crc = crc32((unsigned char *)SDRAM_BASE, length);
	if(crc != got_crc) {
		printf("CRC failed (expected %08x, got %08x)\n", crc, got_crc);
		return;
	}
	boot(0, 0, 0, rescue, SDRAM_BASE);
}
