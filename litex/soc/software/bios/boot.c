// This file is Copyright (c) 2014-2021 Florent Kermarrec <florent@enjoy-digital.fr>
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
#include <system.h>
#include <string.h>
#include <irq.h>

#include <generated/mem.h>
#include <generated/csr.h>
#include <generated/soc.h>

#include "sfl.h"
#include "boot.h"

#include <libbase/uart.h>

#include <libbase/console.h>
#include <libbase/crc.h>
#include <libbase/jsmn.h>
#include <libbase/progress.h>

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

void __attribute__((noreturn)) boot(unsigned long r1, unsigned long r2, unsigned long r3, unsigned long addr)
{
	printf("Executing booted program at 0x%08lx\n\n", addr);
	printf("--============= \e[1mLiftoff!\e[0m ===============--\n");
#ifdef CSR_UART_BASE
	uart_sync();
#endif
#ifdef CONFIG_CPU_HAS_INTERRUPT
	irq_setmask(0);
	irq_setie(0);
#endif
	flush_cpu_icache();
	flush_cpu_dcache();
	flush_l2_cache();

#if (defined(CONFIG_CPU_TYPE_MOR1KX) || defined(CONFIG_CPU_TYPE_MAROCCHINO)) \
     && defined(CONFIG_CPU_VARIANT_LINUX)
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

#define ACK_TIMEOUT_DELAY CONFIG_CLOCK_FREQUENCY/4
#define CMD_TIMEOUT_DELAY CONFIG_CLOCK_FREQUENCY/16

static void timer0_load(unsigned int value) {
	timer0_en_write(0);
	timer0_reload_write(0);
#ifndef CONFIG_BIOS_NO_DELAYS
	timer0_load_write(value);
#else
	timer0_load_write(0);
#endif
	timer0_en_write(1);
	timer0_update_value_write(1);
}

static int check_ack(void)
{
	int recognized;
	static const char str[SFL_MAGIC_LEN] = SFL_MAGIC_ACK;

	timer0_load(ACK_TIMEOUT_DELAY);
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

#define MAX_FAILURES 256

/* Returns 1 if other boot methods should be tried */
int serialboot(void)
{
	struct sfl_frame frame;
	int failures;
	static const char str[SFL_MAGIC_LEN+1] = SFL_MAGIC_REQ;
	const char *c;
	int ack_status;

	printf("Booting from serial...\n");
	printf("Press Q or ESC to abort boot completely.\n");

	/* Send the serialboot "magic" request to Host and wait for ACK_OK */
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
	failures = 0;
	while(1) {
		int i;
		int timeout;
		int computed_crc;
		int received_crc;

		/* Get one Frame */
		i = 0;
		timeout = 1;
		while((i == 0) || timer0_value_read()) {
			if (uart_read_nonblock()) {
				if (i == 0) {
					timer0_load(CMD_TIMEOUT_DELAY);
					frame.payload_length = uart_read();
				}
				if (i == 1) frame.crc[0] = uart_read();
				if (i == 2) frame.crc[1] = uart_read();
				if (i == 3) frame.cmd    = uart_read();
				if (i >= 4) {
					frame.payload[i-4] = uart_read();
					if (i == (frame.payload_length + 4 - 1)) {
						timeout = 0;
						break;
					}
				}
				i++;
			}
			timer0_update_value_write(1);
		}

		/* Check Timeout */
		if (timeout) {
			/* Acknowledge the Timeout and continue with a new frame */
			uart_write(SFL_ACK_ERROR);
			continue;
		}

		/* Check Frame CRC */
		received_crc = ((int)frame.crc[0] << 8)|(int)frame.crc[1];
		computed_crc = crc16(&frame.cmd, frame.payload_length + 1);
		if(computed_crc != received_crc) {
			/* Acknowledge the CRC error */
			uart_write(SFL_ACK_CRCERROR);

			/* Increment failures and exit when max is reached */
			failures++;
			if(failures == MAX_FAILURES) {
				printf("Too many consecutive errors, aborting");
				return 1;
			}
			continue;
		}

		/* Execute Frame CMD */
		switch(frame.cmd) {
			/* On SFL_CMD_ABORT ... */
			case SFL_CMD_ABORT:
				/* Reset failures */
				failures = 0;
				/* Acknowledge and exit */
				uart_write(SFL_ACK_SUCCESS);
				return 1;

			/* On SFL_CMD_LOAD... */
			case SFL_CMD_LOAD: {
				char *load_addr;

				/* Reset failures */
				failures = 0;

				/* Copy payload */
				load_addr = (char *)(uintptr_t) get_uint32(&frame.payload[0]);
				memcpy(load_addr, &frame.payload[4], frame.payload_length - 4);

				/* Acknowledge and continue */
				uart_write(SFL_ACK_SUCCESS);
				break;
			}
			/* On SFL_CMD_ABORT ... */
			case SFL_CMD_JUMP: {
				uint32_t jump_addr;

				/* Reset failures */
				failures = 0;

				/* Acknowledge and jump */
				uart_write(SFL_ACK_SUCCESS);
				jump_addr = get_uint32(&frame.payload[0]);
				boot(0, 0, 0, jump_addr);
				break;
			}
			default:
				/* Increment failures */
				failures++;

				/* Acknowledge the UNKNOWN cmd */
				uart_write(SFL_ACK_UNKNOWN);

				/* Increment failures and exit when max is reached */
				if(failures == MAX_FAILURES) {
					printf("Too many consecutive errors, aborting");
					return 1;
				}

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

#ifndef TFTP_SERVER_PORT
#define TFTP_SERVER_PORT 69
#endif

static unsigned char macadr[6] = {0x10, 0xe2, 0xd5, 0x00, 0x00, 0x00};

#ifdef LOCALIP1
static unsigned int local_ip[4] = {LOCALIP1, LOCALIP2, LOCALIP3, LOCALIP4};
#else
static unsigned int local_ip[4] = {192, 168, 1, 50};
#endif

#ifdef REMOTEIP1
static unsigned int remote_ip[4] = {REMOTEIP1, REMOTEIP2, REMOTEIP3, REMOTEIP4};
#else
static unsigned int remote_ip[4] = {192, 168, 1, 100};
#endif

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

#ifdef ETH_DYNAMIC_IP

static uint8_t parse_ip(const char * ip_address, unsigned int * ip_to_change)
{
	uint8_t n = 0;
	uint8_t k = 0;
	uint8_t i;
	uint8_t size = strlen(ip_address);
	unsigned int ip_to_set[4];
	char buf[3];

	if (size < 7 || size > 15) {
		printf("Error: Invalid IP address length.");
		return -1;
	}

	/* Extract numbers from input, check for potential errors */
	for (i = 0; i < size; i++) {
		if ((ip_address[i] == '.' && k != 0) || (ip_address[i] == '\n' && i == size - 1)) {
			ip_to_set[n] = atoi(buf);
			n++;
			k = 0;
			memset(buf, '\0', sizeof(buf));
		} else if (ip_address[i] >= '0' && ip_address[i] <= '9' && k < 3) {
			buf[k] = ip_address[i];
			k++;
		} else {
			printf("Error: Invalid IP address format. Correct format is \"X.X.X.X\".");
			return -1;
		}
	}
	ip_to_set[n] = atoi(buf);

	/* Check if a correct number of numbers was extracted from the input*/
	if (n != 3) {
		printf("Error: Invalid IP address format. Correct format is \"X.X.X.X\".");
		return -1;
	}

	/* Set the extracted IP address as local or remote ip */
	for (i = 0; i <= n; i++) {
		ip_to_change[i] = ip_to_set[i];
	}
	return 0;
}

void set_local_ip(const char * ip_address)
{
	if (parse_ip(ip_address, local_ip) == 0) {
		udp_set_ip(IPTOINT(local_ip[0], local_ip[1], local_ip[2], local_ip[3]));
		printf("Local IP: %d.%d.%d.%d", local_ip[0], local_ip[1], local_ip[2], local_ip[3]);
	}
}

void set_remote_ip(const char * ip_address)
{
	if (parse_ip(ip_address, remote_ip) == 0) {
		printf("Remote IP: %d.%d.%d.%d", remote_ip[0], remote_ip[1], remote_ip[2], remote_ip[3]);
	}
}

static uint8_t parse_mac_addr(const char * mac_address)
{
	uint8_t n = 0;
	uint8_t k = 0;
	uint8_t i;
	uint8_t size = strlen(mac_address);
	unsigned int mac_to_set[6];
	char buf[2];

	if (size != 17) {
		printf("Error: Invalid MAC address length.");
		return -1;
	}

	/* Extract numbers from input, check for potential errors */
	for (i = 0; i < size; i++) {
		if ((mac_address[i] == ':' && k != 0) || (mac_address[i] == '\n' && i == size - 1)) {
			mac_to_set[n] = strtol(buf, NULL, 16);
			n++;
			k = 0;
			memset(buf, '\0', sizeof(buf));
		} else if (((mac_address[i] >= '0' && mac_address[i] <= '9') ||
			(mac_address[i] >= 'a' && mac_address[i] <= 'f') ||
			(mac_address[i] >= 'A' && mac_address[i] <= 'F')) && k < 2) {
			buf[k] = mac_address[i];
			k++;
		} else {
			printf("Error: Invalid MAC address format. Correct format is \"XX:XX:XX:XX:XX:XX\".");
			return -1;
		}
	}
	mac_to_set[n] = strtol(buf, NULL, 16);

	/* Check if correct number of numbers was extracted from input */
	if (n != 5) {
		printf("Error: Invalid MAC address format. Correct format is \"XX:XX:XX:XX:XX:XX\".");
		return -1;
	}

	/* Set the extracted MAC address as macadr */
	for (i = 0; i <= n; i++) {
		macadr[i] = mac_to_set[i];
	}
	return 0;
}

void set_mac_addr(const char * mac_address)
{
	if (parse_mac_addr(mac_address) == 0) {
		udp_set_mac(macadr);
		printf("MAC address : %x:%x:%x:%x:%x:%x", macadr[0], macadr[1], macadr[2], macadr[3], macadr[4], macadr[5]);
	}
}

#endif

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

#ifdef MAIN_RAM_BASE
static void netboot_from_bin(const char * filename, unsigned int ip, unsigned short tftp_port)
{
	int size;
	size = copy_file_from_tftp_to_ram(ip, tftp_port, filename, (void *)MAIN_RAM_BASE);
	if (size <= 0)
		return;
	boot(0, 0, 0, MAIN_RAM_BASE);
}
#endif

void netboot(int nb_params, char **params)
{
	unsigned int ip;
	char * filename = NULL;

	if (nb_params > 0 )
		filename = params[0];

	printf("Booting from network...\n");

	printf("Local IP: %d.%d.%d.%d\n", local_ip[0], local_ip[1], local_ip[2], local_ip[3]);
	printf("Remote IP: %d.%d.%d.%d\n", remote_ip[0], remote_ip[1], remote_ip[2], remote_ip[3]);

	ip = IPTOINT(remote_ip[0], remote_ip[1], remote_ip[2], remote_ip[3]);
	udp_start(macadr, IPTOINT(local_ip[0], local_ip[1], local_ip[2], local_ip[3]));

	if (filename) {
		printf("Booting from %s (JSON)...\n", filename);
		netboot_from_json(filename, ip, TFTP_SERVER_PORT);
	} else {
		/* Boot from boot.json */
		printf("Booting from boot.json...\n");
		netboot_from_json("boot.json", ip, TFTP_SERVER_PORT);

#ifdef MAIN_RAM_BASE
		/* Boot from boot.bin */
		printf("Booting from boot.bin...\n");
		netboot_from_bin("boot.bin", ip, TFTP_SERVER_PORT);
#endif
	}

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
	unsigned long length;

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
	printf("Copying %s to 0x%08lx (%ld bytes)...\n", filename, ram_address, length);
	init_progression_bar(length);
	offset = 0;
	for (;;) {
		fr = f_read(&file, (void*) ram_address + offset,  0x8000, (UINT *)&br);
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

	fr = f_read(&file, json_buffer, sizeof(json_buffer), (UINT *) &length);

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

#ifdef MAIN_RAM_BASE
static void sdcardboot_from_bin(const char * filename)
{
	uint32_t result;
	result = copy_file_from_sdcard_to_ram(filename, MAIN_RAM_BASE);
	if (result == 0)
		return;
	boot(0, 0, 0, MAIN_RAM_BASE);
}
#endif

void sdcardboot(void)
{
#ifdef CSR_SPISDCARD_BASE
	printf("Booting from SDCard in SPI-Mode...\n");
	fatfs_set_ops_spisdcard();	/* use spisdcard disk access ops */
#endif
#ifdef CSR_SDCORE_BASE
	printf("Booting from SDCard in SD-Mode...\n");
	fatfs_set_ops_sdcard();		/* use sdcard disk access ops */
#endif

	/* Boot from boot.json */
	printf("Booting from boot.json...\n");
	sdcardboot_from_json("boot.json");

#ifdef MAIN_RAM_BASE
	/* Boot from boot.bin */
	printf("Booting from boot.bin...\n");
	sdcardboot_from_bin("boot.bin");
#endif

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
	unsigned long length;

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
	printf("Copying %s to 0x%08lx (%ld bytes)...\n", filename, ram_address, length);
	init_progression_bar(length);
	offset = 0;
	for (;;) {
		fr = f_read(&file, (void*) ram_address + offset,  0x8000, (UINT *) &br);
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

	fr = f_read(&file, json_buffer, sizeof(json_buffer), (UINT *) &length);

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
	fatfs_set_ops_sata();		/* use sata disk access ops */

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
