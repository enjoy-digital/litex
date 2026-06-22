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
#include "helpers.h"

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
/* Boot                                                                  */
/*-----------------------------------------------------------------------*/

extern void boot_helper(unsigned long r1, unsigned long r2, unsigned long r3, unsigned long addr);

void __attribute__((noreturn)) boot(unsigned long r1, unsigned long r2, unsigned long r3, unsigned long addr)
{
	printf("Executing booted program at 0x%08lx\n\n", addr);
	bios_print_section("Liftoff!");
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

#if defined(MAIN_RAM_BASE) || defined(MAIN_RAM_BASE_VA) || defined(SRAM_BASE) || defined(SRAM_BASE_VA)
static int boot_region_max_size(unsigned long addr, unsigned long base, unsigned long size, size_t *max_size)
{
	/* Compare offsets instead of region end so that regions ending exactly at
	   the top of the address space (base + size wrapping to 0) are accepted. */
	if ((addr < base) || ((addr - base) >= size))
		return 0;

	*max_size = size - (addr - base);
	return 1;
}
#endif

static int boot_load_max_size(unsigned long addr, size_t *max_size)
{
	(void)max_size;
	/* Limit boot image loads to known writable memory regions. */
#ifdef MAIN_RAM_BASE
	if (boot_region_max_size(addr, MAIN_RAM_BASE, MAIN_RAM_SIZE, max_size))
		return 1;
#endif
#ifdef MAIN_RAM_BASE_VA
	if (boot_region_max_size(addr, MAIN_RAM_BASE_VA, MAIN_RAM_SIZE, max_size))
		return 1;
#endif
#ifdef SRAM_BASE
	if (boot_region_max_size(addr, SRAM_BASE, SRAM_SIZE, max_size))
		return 1;
#endif
#ifdef SRAM_BASE_VA
	if (boot_region_max_size(addr, SRAM_BASE_VA, SRAM_SIZE, max_size))
		return 1;
#endif

	printf("Error: boot load address 0x%08lx is outside writable memory\n", addr);
	return 0;
}

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
#define CMD_TIMEOUT_DELAY CONFIG_CLOCK_FREQUENCY/4

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

static int serialboot_fail(int *failures)
{
	(*failures)++;
	if(*failures >= MAX_FAILURES) {
		printf("Too many consecutive errors, aborting\n");
		return 1;
	}
	return 0;
}

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
		timer0_load(CMD_TIMEOUT_DELAY);
		while(timer0_value_read()) {
			if (uart_read_nonblock()) {
				unsigned char data;
				data = uart_read();
				/* Reload the inter-byte timeout: a full frame can take longer
				   than CMD_TIMEOUT_DELAY at low baudrates. */
				timer0_load(CMD_TIMEOUT_DELAY);
				if (i == 0)
					frame.payload_length = data;
				if (i == 1) frame.crc[0] = data;
				if (i == 2) frame.crc[1] = data;
				if (i == 3) frame.cmd    = data;
				if (i >= 4) {
					frame.payload[i-4] = data;
				}
				if (i == (frame.payload_length + 4 - 1)) {
					timeout = 0;
					break;
				}
				i++;
			}
			timer0_update_value_write(1);
		}

		/* Check Timeout */
		if (timeout) {
			/* Acknowledge the Timeout and continue with a new frame */
			uart_write(SFL_ACK_ERROR);
			if(serialboot_fail(&failures))
				return 1;
			continue;
		}

		/* Check Frame CRC */
		received_crc = ((int)frame.crc[0] << 8)|(int)frame.crc[1];
		computed_crc = crc16(&frame.cmd, frame.payload_length + 1);
		if(computed_crc != received_crc) {
			/* Acknowledge the CRC error */
			uart_write(SFL_ACK_CRCERROR);

			/* Increment failures and exit when max is reached */
			if(serialboot_fail(&failures))
				return 1;
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
				uint32_t load_size;
				size_t max_size;

				if(frame.payload_length < 4) {
					uart_write(SFL_ACK_ERROR);
					if(serialboot_fail(&failures))
						return 1;
					break;
				}

				/* Reset failures */
				failures = 0;

				/* Copy payload when it fits in writable memory */
				load_addr = (char *)(uintptr_t) get_uint32(&frame.payload[0]);
				load_size = frame.payload_length - 4;
				if (!boot_load_max_size((unsigned long)load_addr, &max_size) ||
				    (load_size > max_size)) {
					uart_write(SFL_ACK_ERROR);
					if(serialboot_fail(&failures))
						return 1;
					break;
				}
				memcpy(load_addr, &frame.payload[4], load_size);

#ifdef HAS_CLEAN_CPU_DCACHE_RANGE
				if(load_size != 0)
					clean_cpu_dcache_range(load_addr, load_size);
#endif

				/* Acknowledge and continue */
				uart_write(SFL_ACK_SUCCESS);
				break;
			}
			/* On SFL_CMD_JUMP ... */
			case SFL_CMD_JUMP: {
				uint32_t jump_addr;

				if(frame.payload_length < 4) {
					uart_write(SFL_ACK_ERROR);
					if(serialboot_fail(&failures))
						return 1;
					break;
				}

				/* Reset failures */
				failures = 0;

				/* Acknowledge and jump */
				uart_write(SFL_ACK_SUCCESS);
				jump_addr = get_uint32(&frame.payload[0]);
				boot(0, 0, 0, jump_addr);
				break;
			}
			default:
				/* Acknowledge the UNKNOWN cmd */
				uart_write(SFL_ACK_UNKNOWN);

				/* Increment failures and exit when max is reached */
				if(serialboot_fail(&failures))
					return 1;

				break;
		}
	}
	return 1;
}

#endif

#if defined(CSR_ETHMAC_BASE) || defined(CSR_SPISDCARD_BASE) || defined(CSR_SDCARD_BASE) || defined(CSR_SATA_SECTOR2MEM_BASE)
static int json_token_to_string(char *dst, size_t dst_size, const char *json, jsmntok_t *token)
{
	int len;

	if ((token->start < 0) || (token->end < token->start))
		return 0;
	len = token->end - token->start;
	if (len >= (int)dst_size)
		return 0;
	memcpy(dst, json + token->start, len);
	dst[len] = 0;
	return 1;
}

static int boot_parse_address(const char *value, unsigned long *address)
{
	char *end;

	*address = strtoul(value, &end, 0);
	if ((end == value) || (*end != 0)) {
		printf("Error: invalid boot address \"%s\"\n", value);
		return 0;
	}
	return 1;
}

/* Keep the JSON buffer static to limit stack pressure in the boot paths. This
 * is especially useful on 64-bit CPUs or when FatFs also needs temporary stack
 * storage while reading boot.json.
 */
#define BOOT_JSON_BUFFER_SIZE 1024

static char boot_json_buffer[BOOT_JSON_BUFFER_SIZE];

typedef int (*boot_json_load_cb)(void *opaque, const char *filename,
	unsigned long load_addr, size_t max_size);

static void boot_from_json_buffer(const char *json_buffer, int size,
	boot_json_load_cb load_cb, void *opaque)
{
	int i;
	int count;

	/* json_name must accommodate long filenames (FatFs is built with LFN
	   support), but keep these scratch buffers off .bss. */
	char json_name[256];
	char json_value[64];

	unsigned long boot_r1 = 0;
	unsigned long boot_r2 = 0;
	unsigned long boot_r3 = 0;
	unsigned long boot_addr = 0;

	uint8_t image_found = 0;
	uint8_t boot_addr_found = 0;

	/* Parse JSON file */
	static jsmntok_t t[64];
	jsmn_parser p;
	jsmn_init(&p);
	count = jsmn_parse(&p, json_buffer, size, t, sizeof(t)/sizeof(*t));
	if (count < 0) {
		if (count == JSMN_ERROR_NOMEM)
			printf("Error: too many entries in boot JSON (max %d tokens)\n",
				(int)(sizeof(t)/sizeof(*t)));
		else
			printf("Error: failed to parse boot JSON (%d)\n", count);
		return;
	}
	for (i=0; i<count-1; i++) {
		/* Elements are JSON strings with 1 children */
		if ((t[i].type == JSMN_STRING) && (t[i].size == 1)) {
			/* Get Element's filename. Abort instead of skipping the entry:
			   booting with one of the listed images missing (e.g. a kernel
			   without its device tree) would fail in harder-to-debug ways. */
			if (!json_token_to_string(json_name, sizeof(json_name), json_buffer, &t[i])) {
				printf("Error: boot JSON filename is too long\n");
				return;
			}
			/* Get Element's address */
			if (!json_token_to_string(json_value, sizeof(json_value), json_buffer, &t[i+1])) {
				printf("Error: boot JSON value for \"%s\" is too long\n", json_name);
				return;
			}
			/* Skip bootargs (optional) */
			if (strcmp(json_name, "bootargs") == 0) {
				continue;
			}
			/* Get boot addr (optional) */
			else if (strcmp(json_name, "addr") == 0) {
				if (!boot_parse_address(json_value, &boot_addr))
					return;
				boot_addr_found = 1;
			}
			/* Get boot r1 (optional) */
			else if (strcmp(json_name, "r1") == 0) {
				if (!boot_parse_address(json_value, &boot_r1))
					return;
			}
			/* Get boot r2 (optional) */
			else if (strcmp(json_name, "r2") == 0) {
				if (!boot_parse_address(json_value, &boot_r2))
					return;
			}
			/* Get boot r3 (optional) */
			else if (strcmp(json_name, "r3") == 0) {
				if (!boot_parse_address(json_value, &boot_r3))
					return;
			/* Copy Image to address */
			} else {
				unsigned long load_addr;
				size_t max_size;

				if (!boot_parse_address(json_value, &load_addr))
					return;
				if (!boot_load_max_size(load_addr, &max_size))
					return;
				if (!load_cb(opaque, json_name, load_addr, max_size))
					return;
				image_found = 1;
				if (boot_addr_found == 0) /* Boot to last Image address if no bootargs.addr specified */
					boot_addr = load_addr;
			}
		}
	}

	/* Boot */
	if (image_found)
		boot(boot_r1, boot_r2, boot_r3, boot_addr);
	else
		printf("Error: no boot image found in boot JSON\n");
}
#endif

/*-----------------------------------------------------------------------*/
/* Ethernet Boot                                                         */
/*-----------------------------------------------------------------------*/

#ifdef CSR_ETHMAC_BASE

#ifndef TFTP_SERVER_PORT
#define TFTP_SERVER_PORT 69
#endif

#ifdef MACADDR1
static unsigned char macadr[6] = {MACADDR1, MACADDR2, MACADDR3, MACADDR4, MACADDR5, MACADDR6};
#else
static unsigned char macadr[6] = {0x10, 0xe2, 0xd5, 0x00, 0x00, 0x00};
#endif

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
const char *filename, char *buffer, size_t max_size)
{
	int size;
	printf("Copying %s to %p... ", filename, buffer);
	size = tftp_get(ip, server_port, filename, buffer, max_size);
	if(size > 0)
		printf("(%d bytes)", size);
	printf("\n");
	return size;
}

struct netboot_json_ctx {
	unsigned int ip;
	unsigned short tftp_port;
};

static int netboot_json_load(void *opaque, const char *filename,
	unsigned long load_addr, size_t max_size)
{
	struct netboot_json_ctx *ctx = opaque;

	/* Copy Image from Network to address */
	return copy_file_from_tftp_to_ram(ctx->ip, ctx->tftp_port, filename,
		(void *)load_addr, max_size) > 0;
}

#ifdef ETH_DYNAMIC_IP

int parse_ip(const char *ip_address, unsigned int *ip_to_change)
{
	unsigned int ip_to_set[4];
	const char *p = ip_address;
	char *end;

	/* Extract numbers from input, check for potential errors */
	for (int i = 0; i < 4; i++) {
		unsigned long octet;

		if ((*p < '0') || (*p > '9')) {
			printf("Error: invalid IP address format; expected X.X.X.X\n");
			return -1;
		}

		octet = strtoul(p, &end, 10);
		if ((end == p) || (octet > 255)) {
			printf("Error: invalid IP address octet\n");
			return -1;
		}
		ip_to_set[i] = octet;

		if (i == 3) {
			while ((*end == '\r') || (*end == '\n'))
				end++;
			if (*end != 0) {
				printf("Error: invalid IP address format; expected X.X.X.X\n");
				return -1;
			}
		} else {
			if (*end != '.') {
				printf("Error: invalid IP address format; expected X.X.X.X\n");
				return -1;
			}
			p = end + 1;
		}
	}

	/* Set the extracted IP address as local or remote ip */
	for (int i = 0; i < 4; i++)
		ip_to_change[i] = ip_to_set[i];

	return 0;
}

void set_local_ip(const char * ip_address)
{
	if (parse_ip(ip_address, local_ip) == 0) {
		udp_set_ip(IPTOINT(local_ip[0], local_ip[1], local_ip[2], local_ip[3]));
		printf("Local IP: %d.%d.%d.%d\n", local_ip[0], local_ip[1], local_ip[2], local_ip[3]);
		net_init();
	}
}

void set_remote_ip(const char * ip_address)
{
	if (parse_ip(ip_address, remote_ip) == 0) {
		printf("Remote IP: %d.%d.%d.%d\n", remote_ip[0], remote_ip[1], remote_ip[2], remote_ip[3]);
	}
}

static int parse_mac_addr(const char *mac_address)
{
	unsigned char mac_to_set[6];
	size_t size = strlen(mac_address);
	char buf[3] = {0};

	while ((size > 0) && ((mac_address[size - 1] == '\r') || (mac_address[size - 1] == '\n')))
		size--;

	if (size != 17) {
		printf("Error: invalid MAC address length\n");
		return -1;
	}

	/* Extract numbers from input, check for potential errors */
	for (int i = 0; i < 6; i++) {
		const char *group = &mac_address[3*i];

		if (!(((group[0] >= '0') && (group[0] <= '9')) ||
		      ((group[0] >= 'a') && (group[0] <= 'f')) ||
		      ((group[0] >= 'A') && (group[0] <= 'F'))) ||
		    !(((group[1] >= '0') && (group[1] <= '9')) ||
		      ((group[1] >= 'a') && (group[1] <= 'f')) ||
		      ((group[1] >= 'A') && (group[1] <= 'F'))) ||
		    ((i < 5) && (group[2] != ':'))) {
			printf("Error: invalid MAC address format; expected XX:XX:XX:XX:XX:XX\n");
			return -1;
		}

		buf[0] = group[0];
		buf[1] = group[1];
		mac_to_set[i] = strtoul(buf, NULL, 16);
	}

	/* Set the extracted MAC address as macadr */
	for (int i = 0; i < 6; i++)
		macadr[i] = mac_to_set[i];

	return 0;
}

void set_mac_addr(const char * mac_address)
{
	if (parse_mac_addr(mac_address) == 0) {
		udp_set_mac(macadr);
		printf("MAC address: %02x:%02x:%02x:%02x:%02x:%02x\n",
			macadr[0], macadr[1], macadr[2], macadr[3], macadr[4], macadr[5]);
		net_init();
	}
}

#endif

static void netboot_from_json(const char * filename, unsigned int ip, unsigned short tftp_port)
{
	int size;
	struct netboot_json_ctx ctx;

	/* Read JSON file */
	size = tftp_get(ip, tftp_port, filename,
		boot_json_buffer, sizeof(boot_json_buffer) - 1);
	if (size <= 0)
		return;
	boot_json_buffer[size] = 0;

	/* Parse JSON file */
	ctx.ip = ip;
	ctx.tftp_port = tftp_port;
	boot_from_json_buffer(boot_json_buffer, size, netboot_json_load, &ctx);
}

#ifdef MAIN_RAM_BASE_VA
static void netboot_from_bin(const char * filename, unsigned int ip, unsigned short tftp_port)
{
	int size;
	size = copy_file_from_tftp_to_ram(ip, tftp_port, filename, (void *)MAIN_RAM_BASE_VA, MAIN_RAM_SIZE);
	if (size <= 0)
		return;
	boot(0, 0, 0, MAIN_RAM_BASE_VA);
}
#endif

void net_init(void) {
	printf("Local IP: %d.%d.%d.%d\n", local_ip[0], local_ip[1], local_ip[2], local_ip[3]);
	udp_start(macadr, IPTOINT(local_ip[0], local_ip[1], local_ip[2], local_ip[3]));
}

void netboot(int nb_params, char **params)
{
	unsigned int ip;
	char * filename = NULL;

	if (nb_params > 0 )
		filename = params[0];

	printf("Booting from network...\n");

	net_init();
	printf("Remote IP: %d.%d.%d.%d\n", remote_ip[0], remote_ip[1], remote_ip[2], remote_ip[3]);

	ip = IPTOINT(remote_ip[0], remote_ip[1], remote_ip[2], remote_ip[3]);

	if (filename) {
		printf("Booting from %s (JSON)...\n", filename);
		netboot_from_json(filename, ip, TFTP_SERVER_PORT);
	} else {
#ifndef ETH_NETBOOT_SKIP_JSON
		/* Boot from boot.json */
		printf("Booting from boot.json...\n");
		netboot_from_json("boot.json", ip, TFTP_SERVER_PORT);
#endif /* ETH_NETBOOT_SKIP_JSON */

#ifdef MAIN_RAM_BASE_VA
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

/* Sanity limit on the flash image length field (catches erased/garbage
   flash). Defaults to the Main RAM size when available since the image has to
   fit there anyway; override with FLASH_BOOT_MAX_SIZE if needed. */
#ifndef FLASH_BOOT_MAX_SIZE
#ifdef MAIN_RAM_SIZE
#define FLASH_BOOT_MAX_SIZE MAIN_RAM_SIZE
#else
#define FLASH_BOOT_MAX_SIZE (16*1024*1024)
#endif
#endif

static unsigned int check_image_in_flash(unsigned int base_address)
{
	uint32_t length;
	uint32_t crc;
	uint32_t got_crc;

	length = MMPTR(base_address);
	if((length < 32) || (length > FLASH_BOOT_MAX_SIZE)) {
		printf("Error: invalid image length 0x%08lx\n", (unsigned long)length);
		return 0;
	}

	crc = MMPTR(base_address + 4);
	got_crc = crc32((unsigned char *)(base_address + 8), length);
	if(crc != got_crc) {
		printf("CRC failed (expected %08lx, got %08lx)\n", (unsigned long)crc, (unsigned long)got_crc);
		return 0;
	}

	return length;
}

#if defined(MAIN_RAM_BASE_VA) && defined(FLASH_BOOT_ADDRESS)
static int copy_image_from_flash_to_ram(unsigned int flash_address, unsigned long ram_address)
{
	uint32_t length;
	uint32_t offset;

	length = check_image_in_flash(flash_address);
	if(length > 0) {
		size_t max_size;

		if (!boot_load_max_size(ram_address, &max_size))
			return 0;
		if (length > max_size) {
			printf("Error: image is too large for destination (0x%08lx > 0x%08lx bytes)\n",
				(unsigned long)length, (unsigned long)max_size);
			return 0;
		}
		printf("Copying 0x%08x to 0x%08lx (%lu bytes)...\n", flash_address, ram_address, (unsigned long)length);
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
	printf("Booting from flash...\n");

#ifdef MAIN_RAM_BASE_VA
	/* When Main RAM is available, copy the code from the Flash and execute it
	from Main RAM since faster. The image is checked as part of the copy, no
	need to check it twice (the CRC over flash is slow). */
	if(!copy_image_from_flash_to_ram(FLASH_BOOT_ADDRESS, MAIN_RAM_BASE_VA))
		return;
	boot(0, 0, 0, MAIN_RAM_BASE_VA);
#else
	if(!check_image_in_flash(FLASH_BOOT_ADDRESS))
		return;
	/* When Main RAM is not available, execute the code directly from Flash (XIP).
       The code starts after (a) length and (b) CRC -- both uint32_t */
	boot(0, 0, 0, (FLASH_BOOT_ADDRESS + 2 * sizeof(uint32_t)));
#endif
}

#endif

/*-----------------------------------------------------------------------*/
/* SDCard Boot                                                           */
/*-----------------------------------------------------------------------*/

#if defined(CSR_SPISDCARD_BASE) || defined(CSR_SDCARD_BASE)

static int copy_file_from_sdcard_to_ram(const char * filename, unsigned long ram_address, size_t max_size)
{
	FRESULT fr;
	FATFS fs;
	FIL file;
	uint32_t br;
	uint32_t offset;
	unsigned long length;

	fr = f_mount(&fs, "", 1);
	if (fr != FR_OK) {
		printf("Error: filesystem mount failed (FatFs error %d)\n", fr);
		return 0;
	}
	fr = f_open(&file, filename, FA_READ);
	if (fr != FR_OK) {
		printf("%s file not found.\n", filename);
		f_mount(0, "", 0);
		return 0;
	}

	length = f_size(&file);
	if (length > max_size) {
		printf("Error: %s is too large for destination (0x%08lx > 0x%08lx bytes)\n",
			filename, length, (unsigned long)max_size);
		f_close(&file);
		f_mount(0, "", 0);
		return 0;
	}
	printf("Copying %s to 0x%08lx (%ld bytes)...\n", filename, ram_address, length);
	init_progression_bar(length);
	offset = 0;
	for (;;) {
		fr = f_read(&file, (void*) ram_address + offset,  0x8000, (UINT *)&br);
		if (fr != FR_OK) {
			printf("Error: file read failed\n");
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

static int sdcardboot_json_load(void *opaque, const char *filename,
	unsigned long load_addr, size_t max_size)
{
	(void)opaque;

	/* Copy Image from SDCard to address */
	return copy_file_from_sdcard_to_ram(filename, load_addr, max_size) != 0;
}

static void sdcardboot_from_json(const char * filename)
{
	FRESULT fr;
	FATFS fs;
	FIL file;

	uint32_t length;

	/* Read JSON file */
	fr = f_mount(&fs, "", 1);
	if (fr != FR_OK) {
		printf("Error: filesystem mount failed (FatFs error %d)\n", fr);
		return;
	}
	fr = f_open(&file, filename, FA_READ);
	if (fr != FR_OK) {
		printf("%s file not found.\n", filename);
		f_mount(0, "", 0);
		return;
	}

	length = f_size(&file);
	if (length >= sizeof(boot_json_buffer)) {
		printf("Error: %s is too large for boot JSON buffer\n", filename);
		f_close(&file);
		f_mount(0, "", 0);
		return;
	}
	fr = f_read(&file, boot_json_buffer,
		sizeof(boot_json_buffer) - 1, (UINT *) &length);

	/* Close JSON file */
	f_close(&file);
	f_mount(0, "", 0);
	if (fr != FR_OK)
		return;
	boot_json_buffer[length] = 0;

	/* Parse JSON file */
	boot_from_json_buffer(boot_json_buffer, length, sdcardboot_json_load, NULL);
}

#ifdef MAIN_RAM_BASE_VA
static void sdcardboot_from_bin(const char * filename)
{
	uint32_t result;
	result = copy_file_from_sdcard_to_ram(filename, MAIN_RAM_BASE_VA, MAIN_RAM_SIZE);
	if (result == 0)
		return;
	boot(0, 0, 0, MAIN_RAM_BASE_VA);
}
#endif

void sdcardboot(int nb_params, char **params)
{
	char * filename = NULL;

	if (nb_params > 0)
		filename = params[0];

#ifdef CSR_SPISDCARD_BASE
	printf("Booting from SDCard in SPI-Mode...\n");
	fatfs_set_ops_spisdcard();	/* use spisdcard disk access ops */
#endif
#ifdef CSR_SDCARD_BASE
	printf("Booting from SDCard in SD-Mode...\n");
	fatfs_set_ops_sdcard();		/* use sdcard disk access ops */
#endif

	if (filename) {
		printf("Booting from %s (JSON)...\n", filename);
		sdcardboot_from_json(filename);
	} else {
		/* Boot from boot.json */
		printf("Booting from boot.json...\n");
		sdcardboot_from_json("boot.json");

#ifdef MAIN_RAM_BASE_VA
		/* Boot from boot.bin */
		printf("Booting from boot.bin...\n");
		sdcardboot_from_bin("boot.bin");
#endif
	}

	/* Boot failed if we are here... */
	printf("SDCard boot failed.\n");
}
#endif

/*-----------------------------------------------------------------------*/
/* SATA Boot                                                             */
/*-----------------------------------------------------------------------*/

#if defined(CSR_SATA_SECTOR2MEM_BASE)

static int copy_file_from_sata_to_ram(const char * filename, unsigned long ram_address, size_t max_size)
{
	FRESULT fr;
	FATFS fs;
	FIL file;
	uint32_t br;
	uint32_t offset;
	unsigned long length;

	fr = f_mount(&fs, "", 1);
	if (fr != FR_OK) {
		printf("Error: filesystem mount failed (FatFs error %d)\n", fr);
		return 0;
	}
	fr = f_open(&file, filename, FA_READ);
	if (fr != FR_OK) {
		printf("%s file not found.\n", filename);
		f_mount(0, "", 0);
		return 0;
	}

	length = f_size(&file);
	if (length > max_size) {
		printf("Error: %s is too large for destination (0x%08lx > 0x%08lx bytes)\n",
			filename, length, (unsigned long)max_size);
		f_close(&file);
		f_mount(0, "", 0);
		return 0;
	}
	printf("Copying %s to 0x%08lx (%ld bytes)...\n", filename, ram_address, length);
	init_progression_bar(length);
	offset = 0;
	for (;;) {
		fr = f_read(&file, (void*) ram_address + offset,  0x8000, (UINT *) &br);
		if (fr != FR_OK) {
			printf("Error: file read failed\n");
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

static int sataboot_json_load(void *opaque, const char *filename,
	unsigned long load_addr, size_t max_size)
{
	(void)opaque;

	/* Copy Image from SATA to address */
	return copy_file_from_sata_to_ram(filename, load_addr, max_size) != 0;
}

static void sataboot_from_json(const char * filename)
{
	FRESULT fr;
	FATFS fs;
	FIL file;

	uint32_t length;

	/* Read JSON file */
	fr = f_mount(&fs, "", 1);
	if (fr != FR_OK) {
		printf("Error: filesystem mount failed (FatFs error %d)\n", fr);
		return;
	}
	fr = f_open(&file, filename, FA_READ);
	if (fr != FR_OK) {
		printf("%s file not found.\n", filename);
		f_mount(0, "", 0);
		return;
	}

	length = f_size(&file);
	if (length >= sizeof(boot_json_buffer)) {
		printf("Error: %s is too large for boot JSON buffer\n", filename);
		f_close(&file);
		f_mount(0, "", 0);
		return;
	}
	fr = f_read(&file, boot_json_buffer,
		sizeof(boot_json_buffer) - 1, (UINT *) &length);

	/* Close JSON file */
	f_close(&file);
	f_mount(0, "", 0);
	if (fr != FR_OK)
		return;
	boot_json_buffer[length] = 0;

	/* Parse JSON file */
	boot_from_json_buffer(boot_json_buffer, length, sataboot_json_load, NULL);
}

#ifdef MAIN_RAM_BASE_VA
static void sataboot_from_bin(const char * filename)
{
	uint32_t result;
	result = copy_file_from_sata_to_ram(filename, MAIN_RAM_BASE_VA, MAIN_RAM_SIZE);
	if (result == 0)
		return;
	boot(0, 0, 0, MAIN_RAM_BASE_VA);
}
#endif

void sataboot(int nb_params, char **params)
{
	char * filename = NULL;

	if (nb_params > 0)
		filename = params[0];

	printf("Booting from SATA...\n");
	fatfs_set_ops_sata();		/* use sata disk access ops */

	if (filename) {
		printf("Booting from %s (JSON)...\n", filename);
		sataboot_from_json(filename);
	} else {
		/* Boot from boot.json */
		printf("Booting from boot.json...\n");
		sataboot_from_json("boot.json");

#ifdef MAIN_RAM_BASE_VA
		/* Boot from boot.bin */
		printf("Booting from boot.bin...\n");
		sataboot_from_bin("boot.bin");
#endif
	}

	/* Boot failed if we are here... */
	printf("SATA boot failed.\n");
}
#endif
