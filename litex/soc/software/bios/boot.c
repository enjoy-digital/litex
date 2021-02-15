// This file is Copyright (c) 2014-2020 Florent Kermarrec <florent@enjoy-digital.fr>
// This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
// This file is Copyright (c) 2018 Ewen McNeill <ewen@naos.co.nz>
// This file is Copyright (c) 2018 Felix Held <felix-github@felixheld.de>
// This file is Copyright (c) 2019 Gabriel L. Somlo <gsomlo@gmail.com>
// This file is Copyright (c) 2017 Tim 'mithro' Ansell <mithro@mithis.com>
// This file is Copyright (c) 2018 William D. Jones <thor0505@comcast.net>
// License: BSD

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <console.h>
#include <uart.h>
#include <system.h>
#include <crc.h>
#include <string.h>
#include <irq.h>

#include <generated/mem.h>
#include <generated/csr.h>
#include <generated/soc.h>

#include "sfl.h"
#include "boot.h"
#include "jsmn.h"

#include <progress.h>

#include <libliteeth/udp.h>
#include <libliteeth/tftp.h>

#include <liblitesdcard/spisdcard.h>
#include <liblitesdcard/sdcard.h>
#include <liblitesata/sata.h>
#include <libfatfs/ff.h>

/*-----------------------------------------------------------------------*/
/* Helpers                                                               */
/*-----------------------------------------------------------------------*/

#define max(x, y) (((x) > (y)) ? (x) : (y))
#define min(x, y) (((x) < (y)) ? (x) : (y))

/*-----------------------------------------------------------------------*/
/* Boot                                                                  */
/*-----------------------------------------------------------------------*/

extern void boot_helper(unsigned long r1, unsigned long r2, unsigned long r3, unsigned long addr);

static void __attribute__((noreturn)) boot(unsigned long r1, unsigned long r2, unsigned long r3, unsigned long addr)
{
	printf("Executing booted program at 0x%08lx\n\n", addr);
	printf("--============= \e[1mLiftoff!\e[0m ===============--\n");
	uart_sync();
#ifdef CONFIG_CPU_HAS_INTERRUPT
	irq_setmask(0);
	irq_setie(0);
#endif
	flush_cpu_icache();
	flush_cpu_dcache();
	flush_l2_cache();

#if defined(CONFIG_CPU_TYPE_MOR1KX) && defined(CONFIG_CPU_VARIANT_LINUX)
	/* Mainline Linux expects to have exception vector base address set to the
	 * base address of Linux kernel; it also expects to be run with an offset
	 * of 0x100. */
	mtspr(SPR_EVBAR, addr);
	addr += 0x100;
#endif

	boot_helper(r1, r2, r3, addr);
	while(1);
}

enum {
	ACK_TIMEOUT,
	ACK_CANCELLED,
	ACK_OK
};

/*-----------------------------------------------------------------------*/
/* ROM Boot                                                              */
/*-----------------------------------------------------------------------*/

#ifdef ROM_BOOT_ADDRESS
/* Running the application code from ROM is the fastest way to execute code
   and could be interesting when the code is small enough, on large devices
   where many blockrams are available or simply when the execution speed is
   critical. Defining ROM_BOOT_ADDRESS in the SoC will make the BIOS jump to
   it at boot. */
void romboot(void)
{
	boot(0, 0, 0, ROM_BOOT_ADDRESS);
}
#endif

/*-----------------------------------------------------------------------*/
/* Serial Boot                                                           */
/*-----------------------------------------------------------------------*/

#ifdef CSR_UART_BASE

static int check_ack(void)
{
	int recognized;
	static const char str[SFL_MAGIC_LEN] = SFL_MAGIC_ACK;

	timer0_en_write(0);
	timer0_reload_write(0);
#ifndef CONFIG_DISABLE_DELAYS
	timer0_load_write(CONFIG_CLOCK_FREQUENCY/4);
#else
	timer0_load_write(0);
#endif
	timer0_en_write(1);
	timer0_update_value_write(1);
	recognized = 0;
	while(timer0_value_read()) {
		if(uart_read_nonblock()) {
			char c;
			c = uart_read();
			if((c == 'Q') || (c == '\e'))
				return ACK_CANCELLED;
			if(c == str[recognized]) {
				recognized++;
				if(recognized == SFL_MAGIC_LEN)
					return ACK_OK;
			} else {
				if(c == str[0])
					recognized = 1;
				else
					recognized = 0;
			}
		}
		timer0_update_value_write(1);
	}
	return ACK_TIMEOUT;
}

static uint32_t get_uint32(unsigned char* data)
{
	return ((uint32_t) data[0] << 24) |
		   ((uint32_t) data[1] << 16) |
		   ((uint32_t) data[2] << 8) |
			(uint32_t) data[3];
}

#define MAX_FAILED 5

/* Returns 1 if other boot methods should be tried */
int serialboot(void)
{
	struct sfl_frame frame;
	int failed;
	static const char str[SFL_MAGIC_LEN+1] = SFL_MAGIC_REQ;
	const char *c;
	int ack_status;

	printf("Booting from serial...\n");
	printf("Press Q or ESC to abort boot completely.\n");

	/* Send the serialboot "magic" request to Host */
	c = str;
	while(*c) {
		uart_write(*c);
		c++;
	}
	ack_status = check_ack();
	if(ack_status == ACK_TIMEOUT) {
		printf("Timeout\n");
		return 1;
	}
	if(ack_status == ACK_CANCELLED) {
		printf("Cancelled\n");
		return 0;
	}
	/* Assume ACK_OK */

	failed = 0;
	while(1) {
		int i;
		int actualcrc;
		int goodcrc;

		/* Get one Frame */
		frame.payload_length = uart_read();
		frame.crc[0] = uart_read();
		frame.crc[1] = uart_read();
		frame.cmd = uart_read();
		for(i=0;i<frame.payload_length;i++)
			frame.payload[i] = uart_read();

		/* Check Frame CRC (if CMD has a CRC) */
		actualcrc = ((int)frame.crc[0] << 8)|(int)frame.crc[1];
		goodcrc = crc16(&frame.cmd, frame.payload_length+1);
		if(actualcrc != goodcrc) {
			/* Clear out the RX buffer */
			while (uart_read_nonblock()) uart_read();
			failed++;
			if(failed == MAX_FAILED) {
				printf("Too many consecutive errors, aborting");
				return 1;
			}
			uart_write(SFL_ACK_CRCERROR);
			continue;
		}

		/* Execute Frame CMD */
		switch(frame.cmd) {
			case SFL_CMD_ABORT:
				failed = 0;
				uart_write(SFL_ACK_SUCCESS);
				return 1;
			case SFL_CMD_LOAD: {
				char *writepointer;

				failed = 0;
				writepointer = (char *)(uintptr_t) get_uint32(&frame.payload[0]);
				for(i=4;i<frame.payload_length;i++)
					*(writepointer++) = frame.payload[i];
				if (frame.cmd == SFL_CMD_LOAD)
					uart_write(SFL_ACK_SUCCESS);
				break;
			}
			case SFL_CMD_JUMP: {
				uint32_t addr;

				failed = 0;
				addr = get_uint32(&frame.payload[0]);
				uart_write(SFL_ACK_SUCCESS);
				boot(0, 0, 0, addr);
				break;
			}
			default:
				failed++;
				if(failed == MAX_FAILED) {
					printf("Too many consecutive errors, aborting");
					return 1;
				}
				uart_write(SFL_ACK_UNKNOWN);
				break;
		}
	}
	return 1;
}

#endif

/*-----------------------------------------------------------------------*/
/* Ethernet Boot                                                         */
/*-----------------------------------------------------------------------*/

#ifdef CSR_ETHMAC_BASE

#ifndef LOCALIP1
#define LOCALIP1 192
#define LOCALIP2 168
#define LOCALIP3 1
#define LOCALIP4 50
#endif

#ifndef REMOTEIP1
#define REMOTEIP1 192
#define REMOTEIP2 168
#define REMOTEIP3 1
#define REMOTEIP4 100
#endif

#ifndef TFTP_SERVER_PORT
#define TFTP_SERVER_PORT 69
#endif

static const unsigned char macadr[6] = {0x10, 0xe2, 0xd5, 0x00, 0x00, 0x00};

static int copy_file_from_tftp_to_ram(unsigned int ip, unsigned short server_port,
const char *filename, char *buffer)
{
	int size;
	printf("Copying %s to %p... ", filename, buffer);
	size = tftp_get(ip, server_port, filename, buffer);
	if(size > 0)
		printf("(%d bytes)", size);
	printf("\n");
	return size;
}

static void netboot_from_json(const char * filename, unsigned int ip, unsigned short tftp_port)
{
	int size;
	uint8_t i;
	uint8_t count;

	/* FIXME: modify/increase if too limiting */
	char json_buffer[1024];
	char json_name[32];
	char json_value[32];

	unsigned long boot_r1 = 0;
	unsigned long boot_r2 = 0;
	unsigned long boot_r3 = 0;
	unsigned long boot_addr = 0;

	uint8_t image_found = 0;
	uint8_t boot_addr_found = 0;

	/* Read JSON file */
	size = tftp_get(ip, tftp_port, filename, json_buffer);
	if (size <= 0)
		return;

	/* Parse JSON file */
	jsmntok_t t[32];
	jsmn_parser p;
	jsmn_init(&p);
	count = jsmn_parse(&p, json_buffer, strlen(json_buffer), t, sizeof(t)/sizeof(*t));
	for (i=0; i<count-1; i++) {
		memset(json_name,   0, sizeof(json_name));
		memset(json_value,  0, sizeof(json_value));
		/* Elements are JSON strings with 1 children */
		if ((t[i].type == JSMN_STRING) && (t[i].size == 1)) {
			/* Get Element's filename */
			memcpy(json_name, json_buffer + t[i].start, t[i].end - t[i].start);
			/* Get Element's address */
			memcpy(json_value, json_buffer + t[i+1].start, t[i+1].end - t[i+1].start);
			/* Skip bootargs (optional) */
			if (strncmp(json_name, "bootargs", 8) == 0) {
				continue;
			}
			/* Get boot addr (optional) */
			else if (strncmp(json_name, "addr", 4) == 0) {
				boot_addr = strtoul(json_value, NULL, 0);
				boot_addr_found = 1;
			}
			/* Get boot r1 (optional) */
			else if (strncmp(json_name, "r1", 2) == 0) {
				memcpy(json_name, json_buffer + t[i].start, t[i].end - t[i].start);
				boot_r1 = strtoul(json_value, NULL, 0);
			}
			/* Get boot r2 (optional) */
			else if (strncmp(json_name, "r2", 2) == 0) {
				boot_r2 = strtoul(json_value, NULL, 0);
			}
			/* Get boot r3 (optional) */
			else if (strncmp(json_name, "r3", 2) == 0) {
				boot_r3 = strtoul(json_value, NULL, 0);
			/* Copy Image from Network to address */
			} else {
				size = copy_file_from_tftp_to_ram(ip, tftp_port, json_name, (void *)strtoul(json_value, NULL, 0));
				if (size <= 0)
					return;
				image_found = 1;
				if (boot_addr_found == 0) /* Boot to last Image address if no bootargs.addr specified */
					boot_addr = strtoul(json_value, NULL, 0);
			}
		}
	}

	/* Boot */
	if (image_found)
		boot(boot_r1, boot_r2, boot_r3, boot_addr);
}

static void netboot_from_bin(const char * filename, unsigned int ip, unsigned short tftp_port)
{
	int size;
	size = copy_file_from_tftp_to_ram(ip, tftp_port, filename, (void *)MAIN_RAM_BASE);
	if (size <= 0)
		return;
	boot(0, 0, 0, MAIN_RAM_BASE);
}

void netboot(void)
{
	unsigned int ip;


	printf("Booting from network...\n");
	printf("Local IP : %d.%d.%d.%d\n", LOCALIP1, LOCALIP2, LOCALIP3, LOCALIP4);
	printf("Remote IP: %d.%d.%d.%d\n", REMOTEIP1, REMOTEIP2, REMOTEIP3, REMOTEIP4);

	ip = IPTOINT(REMOTEIP1, REMOTEIP2, REMOTEIP3, REMOTEIP4);
	udp_start(macadr, IPTOINT(LOCALIP1, LOCALIP2, LOCALIP3, LOCALIP4));

	/* Boot from boot.json */
	printf("Booting from boot.json...\n");
	netboot_from_json("boot.json", ip, TFTP_SERVER_PORT);

	/* Boot from boot.bin */
	printf("Booting from boot.bin...\n");
	netboot_from_bin("boot.bin", ip, TFTP_SERVER_PORT);

	/* Boot failed if we are here... */
	printf("Network boot failed.\n");
}

#endif

/*-----------------------------------------------------------------------*/
/* Flash Boot                                                            */
/*-----------------------------------------------------------------------*/

#ifdef FLASH_BOOT_ADDRESS

static unsigned int check_image_in_flash(unsigned int base_address)
{
	uint32_t length;
	uint32_t crc;
	uint32_t got_crc;

	length = MMPTR(base_address);
	if((length < 32) || (length > 16*1024*1024)) {
		printf("Error: Invalid image length 0x%08x\n", length);
		return 0;
	}

	crc = MMPTR(base_address + 4);
	got_crc = crc32((unsigned char *)(base_address + 8), length);
	if(crc != got_crc) {
		printf("CRC failed (expected %08x, got %08x)\n", crc, got_crc);
		return 0;
	}

	return length;
}

#if defined(MAIN_RAM_BASE) && defined(FLASH_BOOT_ADDRESS)
static int copy_image_from_flash_to_ram(unsigned int flash_address, unsigned long ram_address)
{
	uint32_t length;
	uint32_t offset;

	length = check_image_in_flash(flash_address);
	if(length > 0) {
		printf("Copying 0x%08x to 0x%08lx (%d bytes)...\n", flash_address, ram_address, length);
		offset = 0;
		init_progression_bar(length);
		while (length > 0) {
			uint32_t chunk_length;
			chunk_length = min(length, 0x8000); /* 32KB chunks */
			memcpy((void *) ram_address + offset, (void*) flash_address + offset + 8, chunk_length);
			offset += chunk_length;
			length -= chunk_length;
			show_progress(offset);
		}
		show_progress(offset);
		printf("\n");
		return 1;
	}

	return 0;
}
#endif

void flashboot(void)
{
	uint32_t length;
	uint32_t result;

	printf("Booting from flash...\n");
	length = check_image_in_flash(FLASH_BOOT_ADDRESS);
	if(!length)
		return;

#ifdef MAIN_RAM_BASE
	/* When Main RAM is available, copy the code from the Flash and execute it
	from Main RAM since faster */
	result = copy_image_from_flash_to_ram(FLASH_BOOT_ADDRESS, MAIN_RAM_BASE);
	if(!result)
		return;
	boot(0, 0, 0, MAIN_RAM_BASE);
#else
	/* When Main RAM is not available, execute the code directly from Flash (XIP).
       The code starts after (a) length and (b) CRC -- both uint32_t */
	boot(0, 0, 0, (FLASH_BOOT_ADDRESS + 2 * sizeof(uint32_t)));
#endif
}

#endif

/*-----------------------------------------------------------------------*/
/* SDCard Boot                                                           */
/*-----------------------------------------------------------------------*/

#if defined(CSR_SPISDCARD_BASE) || defined(CSR_SDCORE_BASE)

static int copy_file_from_sdcard_to_ram(const char * filename, unsigned long ram_address)
{
	FRESULT fr;
	FATFS fs;
	FIL file;
	uint32_t br;
	uint32_t offset;
	uint32_t length;

	fr = f_mount(&fs, "", 1);
	if (fr != FR_OK)
		return 0;
	fr = f_open(&file, filename, FA_READ);
	if (fr != FR_OK) {
		printf("%s file not found.\n", filename);
		f_mount(0, "", 0);
		return 0;
	}

	length = f_size(&file);
	printf("Copying %s to 0x%08lx (%d bytes)...\n", filename, ram_address, length);
	init_progression_bar(length);
	offset = 0;
	for (;;) {
		fr = f_read(&file, (void*) ram_address + offset,  0x8000, &br);
		if (fr != FR_OK) {
			printf("file read error.\n");
			f_close(&file);
			f_mount(0, "", 0);
			return 0;
		}
		if (br == 0)
			break;
		offset += br;
		show_progress(offset);
	}
	show_progress(offset);
	printf("\n");

	f_close(&file);
	f_mount(0, "", 0);

	return 1;
}

static void sdcardboot_from_json(const char * filename)
{
	FRESULT fr;
	FATFS fs;
	FIL file;

	uint8_t i;
	uint8_t count;
	uint32_t length;
	uint32_t result;

	/* FIXME: modify/increase if too limiting */
	char json_buffer[1024];
	char json_name[32];
	char json_value[32];

	unsigned long boot_r1 = 0;
	unsigned long boot_r2 = 0;
	unsigned long boot_r3 = 0;
	unsigned long boot_addr = 0;

	uint8_t image_found = 0;
	uint8_t boot_addr_found = 0;

	/* Read JSON file */
	fr = f_mount(&fs, "", 1);
	if (fr != FR_OK)
		return;
	fr = f_open(&file, filename, FA_READ);
	if (fr != FR_OK) {
		printf("%s file not found.\n", filename);
		f_mount(0, "", 0);
		return;
	}

	fr = f_read(&file, json_buffer, sizeof(json_buffer), &length);

	/* Close JSON file */
	f_close(&file);
	f_mount(0, "", 0);

	/* Parse JSON file */
	jsmntok_t t[32];
	jsmn_parser p;
	jsmn_init(&p);
	count = jsmn_parse(&p, json_buffer, strlen(json_buffer), t, sizeof(t)/sizeof(*t));
	for (i=0; i<count-1; i++) {
		memset(json_name,   0, sizeof(json_name));
		memset(json_value,  0, sizeof(json_value));
		/* Elements are JSON strings with 1 children */
		if ((t[i].type == JSMN_STRING) && (t[i].size == 1)) {
			/* Get Element's filename */
			memcpy(json_name, json_buffer + t[i].start, t[i].end - t[i].start);
			/* Get Element's address */
			memcpy(json_value, json_buffer + t[i+1].start, t[i+1].end - t[i+1].start);
			/* Skip bootargs (optional) */
			if (strncmp(json_name, "bootargs", 8) == 0) {
				continue;
			}
			/* Get boot addr (optional) */
			else if (strncmp(json_name, "addr", 4) == 0) {
				boot_addr = strtoul(json_value, NULL, 0);
				boot_addr_found = 1;
			}
			/* Get boot r1 (optional) */
			else if (strncmp(json_name, "r1", 2) == 0) {
				memcpy(json_name, json_buffer + t[i].start, t[i].end - t[i].start);
				boot_r1 = strtoul(json_value, NULL, 0);
			}
			/* Get boot r2 (optional) */
			else if (strncmp(json_name, "r2", 2) == 0) {
				boot_r2 = strtoul(json_value, NULL, 0);
			}
			/* Get boot r3 (optional) */
			else if (strncmp(json_name, "r3", 2) == 0) {
				boot_r3 = strtoul(json_value, NULL, 0);
			/* Copy Image from SDCard to address */
			} else {
				result = copy_file_from_sdcard_to_ram(json_name, strtoul(json_value, NULL, 0));
				if (result == 0)
					return;
				image_found = 1;
				if (boot_addr_found == 0) /* Boot to last Image address if no bootargs.addr specified */
					boot_addr = strtoul(json_value, NULL, 0);
			}
		}
	}

	/* Boot */
	if (image_found)
		boot(boot_r1, boot_r2, boot_r3, boot_addr);
}

static void sdcardboot_from_bin(const char * filename)
{
	uint32_t result;
	result = copy_file_from_sdcard_to_ram(filename, MAIN_RAM_BASE);
	if (result == 0)
		return;
	boot(0, 0, 0, MAIN_RAM_BASE);
}

void sdcardboot(void)
{
#ifdef CSR_SPISDCARD_BASE
	printf("Booting from SDCard in SPI-Mode...\n");
#endif
#ifdef CSR_SDCORE_BASE
	printf("Booting from SDCard in SD-Mode...\n");
#endif

	/* Boot from boot.json */
	printf("Booting from boot.json...\n");
	sdcardboot_from_json("boot.json");

	/* Boot from boot.bin */
	printf("Booting from boot.bin...\n");
	sdcardboot_from_bin("boot.bin");

	/* Boot failed if we are here... */
	printf("SDCard boot failed.\n");
}
#endif

/*-----------------------------------------------------------------------*/
/* SATA Boot                                                             */
/*-----------------------------------------------------------------------*/

#if defined(CSR_SATA_SECTOR2MEM_BASE)

static int copy_file_from_sata_to_ram(const char * filename, unsigned long ram_address)
{
	FRESULT fr;
	FATFS fs;
	FIL file;
	uint32_t br;
	uint32_t offset;
	uint32_t length;

	fr = f_mount(&fs, "", 1);
	if (fr != FR_OK)
		return 0;
	fr = f_open(&file, filename, FA_READ);
	if (fr != FR_OK) {
		printf("%s file not found.\n", filename);
		f_mount(0, "", 0);
		return 0;
	}

	length = f_size(&file);
	printf("Copying %s to 0x%08lx (%d bytes)...\n", filename, ram_address, length);
	init_progression_bar(length);
	offset = 0;
	for (;;) {
		fr = f_read(&file, (void*) ram_address + offset,  0x8000, &br);
		if (fr != FR_OK) {
			printf("file read error.\n");
			f_close(&file);
			f_mount(0, "", 0);
			return 0;
		}
		if (br == 0)
			break;
		offset += br;
		show_progress(offset);
	}
	show_progress(offset);
	printf("\n");

	f_close(&file);
	f_mount(0, "", 0);

	return 1;
}

static void sataboot_from_json(const char * filename)
{
	FRESULT fr;
	FATFS fs;
	FIL file;

	uint8_t i;
	uint8_t count;
	uint32_t length;
	uint32_t result;

	/* FIXME: modify/increase if too limiting */
	char json_buffer[1024];
	char json_name[32];
	char json_value[32];

	unsigned long boot_r1 = 0;
	unsigned long boot_r2 = 0;
	unsigned long boot_r3 = 0;
	unsigned long boot_addr = 0;

	uint8_t image_found = 0;
	uint8_t boot_addr_found = 0;

	/* Read JSON file */
	fr = f_mount(&fs, "", 1);
	if (fr != FR_OK)
		return;
	fr = f_open(&file, filename, FA_READ);
	if (fr != FR_OK) {
		printf("%s file not found.\n", filename);
		f_mount(0, "", 0);
		return;
	}

	fr = f_read(&file, json_buffer, sizeof(json_buffer), &length);

	/* Close JSON file */
	f_close(&file);
	f_mount(0, "", 0);

	/* Parse JSON file */
	jsmntok_t t[32];
	jsmn_parser p;
	jsmn_init(&p);
	count = jsmn_parse(&p, json_buffer, strlen(json_buffer), t, sizeof(t)/sizeof(*t));
	for (i=0; i<count-1; i++) {
		memset(json_name,   0, sizeof(json_name));
		memset(json_value,  0, sizeof(json_value));
		/* Elements are JSON strings with 1 children */
		if ((t[i].type == JSMN_STRING) && (t[i].size == 1)) {
			/* Get Element's filename */
			memcpy(json_name, json_buffer + t[i].start, t[i].end - t[i].start);
			/* Get Element's address */
			memcpy(json_value, json_buffer + t[i+1].start, t[i+1].end - t[i+1].start);
			/* Skip bootargs (optional) */
			if (strncmp(json_name, "bootargs", 8) == 0) {
				continue;
			}
			/* Get boot addr (optional) */
			else if (strncmp(json_name, "addr", 4) == 0) {
				boot_addr = strtoul(json_value, NULL, 0);
				boot_addr_found = 1;
			}
			/* Get boot r1 (optional) */
			else if (strncmp(json_name, "r1", 2) == 0) {
				memcpy(json_name, json_buffer + t[i].start, t[i].end - t[i].start);
				boot_r1 = strtoul(json_value, NULL, 0);
			}
			/* Get boot r2 (optional) */
			else if (strncmp(json_name, "r2", 2) == 0) {
				boot_r2 = strtoul(json_value, NULL, 0);
			}
			/* Get boot r3 (optional) */
			else if (strncmp(json_name, "r3", 2) == 0) {
				boot_r3 = strtoul(json_value, NULL, 0);
			/* Copy Image from SDCard to address */
			} else {
				result = copy_file_from_sata_to_ram(json_name, strtoul(json_value, NULL, 0));
				if (result == 0)
					return;
				image_found = 1;
				if (boot_addr_found == 0) /* Boot to last Image address if no bootargs.addr specified */
					boot_addr = strtoul(json_value, NULL, 0);
			}
		}
	}

	/* Boot */
	if (image_found)
		boot(boot_r1, boot_r2, boot_r3, boot_addr);
}

static void sataboot_from_bin(const char * filename)
{
	uint32_t result;
	result = copy_file_from_sata_to_ram(filename, MAIN_RAM_BASE);
	if (result == 0)
		return;
	boot(0, 0, 0, MAIN_RAM_BASE);
}

void sataboot(void)
{
	printf("Booting from SATA...\n");

	/* Boot from boot.json */
	printf("Booting from boot.json...\n");
	sataboot_from_json("boot.json");

	/* Boot from boot.bin */
	printf("Booting from boot.bin...\n");
	sataboot_from_bin("boot.bin");

	/* Boot failed if we are here... */
	printf("SATA boot failed.\n");
}
#endif
