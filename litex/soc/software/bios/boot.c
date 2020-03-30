// This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
// This file is Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
// This file is Copyright (c) 2018 Ewen McNeill <ewen@naos.co.nz>
// This file is Copyright (c) 2018 Felix Held <felix-github@felixheld.de>
// This file is Copyright (c) 2019 Gabriel L. Somlo <gsomlo@gmail.com>
// This file is Copyright (c) 2017 Tim 'mithro' Ansell <mithro@mithis.com>
// This file is Copyright (c) 2018 William D. Jones <thor0505@comcast.net>
// License: BSD

#include <stdio.h>
#include <stdint.h>
#include <console.h>
#include <uart.h>
#include <system.h>
#include <crc.h>
#include <string.h>
#include <irq.h>

#include <generated/mem.h>
#include <generated/csr.h>

#ifdef CSR_ETHMAC_BASE
#include <net/microudp.h>
#include <net/tftp.h>
#endif

#ifdef CSR_SPIFLASH_BASE
#include <spiflash.h>
#endif

#include "sfl.h"
#include "boot.h"

extern void boot_helper(unsigned long r1, unsigned long r2, unsigned long r3, unsigned long addr);

static void __attribute__((noreturn)) boot(unsigned long r1, unsigned long r2, unsigned long r3, unsigned long addr)
{
	printf("Executing booted program at 0x%08x\n\n", addr);
	printf("--============= \e[1mLiftoff!\e[0m ===============--\n");
	uart_sync();
	irq_setmask(0);
	irq_setie(0);
/* FIXME: understand why flushing icache on Vexriscv make boot fail  */
#ifndef __vexriscv__
	flush_cpu_icache();
#endif
	flush_cpu_dcache();
#ifdef CONFIG_L2_SIZE
	flush_l2_cache();
#endif

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

static int check_ack(void)
{
	int recognized;
	static const char str[SFL_MAGIC_LEN] = SFL_MAGIC_ACK;

	timer0_en_write(0);
	timer0_reload_write(0);
	timer0_load_write(CONFIG_CLOCK_FREQUENCY/4);
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

	/* send the serialboot "magic" request to Host */
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
	/* assume ACK_OK */

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
		if (frame.cmd != SFL_CMD_LOAD_NO_CRC) {
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
		}

		/* Execute Frame CMD */
		switch(frame.cmd) {
			case SFL_CMD_ABORT:
				failed = 0;
				uart_write(SFL_ACK_SUCCESS);
				return 1;
			case SFL_CMD_LOAD:
			case SFL_CMD_LOAD_NO_CRC: {
				char *writepointer;

				failed = 0;
				writepointer = (char *) get_uint32(&frame.payload[0]);
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
			case SFL_CMD_FLASH: {
#if (defined CSR_SPIFLASH_BASE && defined SPIFLASH_PAGE_SIZE)
				uint32_t addr;

				failed = 0;
				addr = get_uint32(&frame.payload[0]);

				for (i = 4; i < frame.payload_length; i++) {
					// erase page at sector boundaries before writing
					if ((addr & (SPIFLASH_SECTOR_SIZE - 1)) == 0) {
						erase_flash_sector(addr);
					}
					write_to_flash(addr, &frame.payload[i], 1);
					addr++;
				}
				uart_write(SFL_ACK_SUCCESS);
#endif
				break;
			}
			case SFL_CMD_REBOOT:
#ifdef CSR_CTRL_BASE
				uart_write(SFL_ACK_SUCCESS);
				ctrl_reset_write(1);
#endif
				break;
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

#if defined(CONFIG_CPU_TYPE_VEXRISCV) && defined(CONFIG_CPU_VARIANT_LINUX)

#ifndef KERNEL_IMAGE_RAM_OFFSET
#define KERNEL_IMAGE_RAM_OFFSET 0x00000000
#endif
#ifndef ROOTFS_IMAGE_RAM_OFFSET
#define ROOTFS_IMAGE_RAM_OFFSET 0x00800000
#endif
#ifndef DEVICE_TREE_IMAGE_RAM_OFFSET
#define DEVICE_TREE_IMAGE_RAM_OFFSET 0x01000000
#endif
#ifndef EMULATOR_IMAGE_RAM_OFFSET
#define EMULATOR_IMAGE_RAM_OFFSET 0x01100000
#endif

#endif

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

#define DEFAULT_TFTP_SERVER_PORT 69  /* IANA well known port: UDP/69 */
#ifndef TFTP_SERVER_PORT
#define TFTP_SERVER_PORT DEFAULT_TFTP_SERVER_PORT
#endif

static int tftp_get_v(unsigned int ip, unsigned short server_port,
const char *filename, char *buffer)
{
	int r;

	r = tftp_get(ip, server_port, filename, buffer);
	if(r > 0)
		printf("Downloaded %d bytes from %s over TFTP to 0x%08x\n", r, filename, buffer);
	else
		printf("Unable to download %s over TFTP\n", filename);
	return r;
}

static const unsigned char macadr[6] = {0x10, 0xe2, 0xd5, 0x00, 0x00, 0x00};


#if defined(CONFIG_CPU_TYPE_VEXRISCV) && defined(CONFIG_CPU_VARIANT_LINUX)
static int try_get_kernel_rootfs_dtb_emulator(unsigned int ip, unsigned short tftp_port)
{
	unsigned long tftp_dst_addr;
	int size;

	tftp_dst_addr = MAIN_RAM_BASE + KERNEL_IMAGE_RAM_OFFSET;
	size = tftp_get_v(ip, tftp_port, "Image", (void *)tftp_dst_addr);
	if (size <= 0) {
		printf("Network boot failed\n");
		return 0;
	}

	tftp_dst_addr = MAIN_RAM_BASE + ROOTFS_IMAGE_RAM_OFFSET;
	size = tftp_get_v(ip, tftp_port, "rootfs.cpio", (void *)tftp_dst_addr);
	if(size <= 0) {
		printf("No rootfs.cpio found\n");
		return 0;
	}

	tftp_dst_addr = MAIN_RAM_BASE + DEVICE_TREE_IMAGE_RAM_OFFSET;
	size = tftp_get_v(ip, tftp_port, "rv32.dtb", (void *)tftp_dst_addr);
	if(size <= 0) {
		printf("No rv32.dtb found\n");
		return 0;
	}

	tftp_dst_addr =  MAIN_RAM_BASE + EMULATOR_IMAGE_RAM_OFFSET;
	size = tftp_get_v(ip, tftp_port, "emulator.bin", (void *)tftp_dst_addr);
	if(size <= 0) {
		printf("No emulator.bin found\n");
		return 0;
	}

	return 1;
}
#endif

void netboot(void)
{
	int size;
	unsigned int ip;
	unsigned long tftp_dst_addr;
	unsigned short tftp_port;

	printf("Booting from network...\n");
	printf("Local IP : %d.%d.%d.%d\n", LOCALIP1, LOCALIP2, LOCALIP3, LOCALIP4);
	printf("Remote IP: %d.%d.%d.%d\n", REMOTEIP1, REMOTEIP2, REMOTEIP3, REMOTEIP4);

	ip = IPTOINT(REMOTEIP1, REMOTEIP2, REMOTEIP3, REMOTEIP4);

	microudp_start(macadr, IPTOINT(LOCALIP1, LOCALIP2, LOCALIP3, LOCALIP4));

	tftp_port = TFTP_SERVER_PORT;
	printf("Fetching from: UDP/%d\n", tftp_port);

#if defined(CONFIG_CPU_TYPE_VEXRISCV) && defined(CONFIG_CPU_VARIANT_LINUX)
	if(try_get_kernel_rootfs_dtb_emulator(ip, tftp_port))
	{
		boot(0, 0, 0, MAIN_RAM_BASE + EMULATOR_IMAGE_RAM_OFFSET);
		return;
	}
	printf("Unable to download Linux images, falling back to boot.bin\n");
#endif
	tftp_dst_addr = MAIN_RAM_BASE;
	size = tftp_get_v(ip, tftp_port, "boot.bin", (void *)tftp_dst_addr);
	if (size <= 0) {
		printf("Network boot failed\n");
		return;
	}

	boot(0, 0, 0, MAIN_RAM_BASE);
}

#endif

#ifdef FLASH_BOOT_ADDRESS

/* On systems with exernal SDRAM we copy out of the SPI flash into the SDRAM
   before running, as it is faster.  If we have no SDRAM then we have to
   execute directly out of the SPI flash. */
#ifdef MAIN_RAM_BASE
#define FIRMWARE_BASE_ADDRESS MAIN_RAM_BASE
#else
/* Firmware code starts after (a) length and (b) CRC -- both unsigned ints */
#define FIRMWARE_BASE_ADDRESS (FLASH_BOOT_ADDRESS + 2 * sizeof(unsigned int))
#endif

static unsigned int check_image_in_flash(unsigned int base_address)
{
	unsigned int length;
	unsigned int crc;
	unsigned int got_crc;

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

#if defined(MAIN_RAM_BASE) && defined(CONFIG_CPU_TYPE_VEXRISCV) && defined(CONFIG_CPU_VARIANT_LINUX)
static int copy_image_from_flash_to_ram(unsigned int flash_address, unsigned int ram_address)
{
	unsigned int length;

	length = check_image_in_flash(flash_address);
	if(length > 0) {
		printf("Copying %d bytes from 0x%08x to 0x%08x...\n", length, flash_address, ram_address);
		// skip length and crc
		memcpy((void *)ram_address, (void *)flash_address + 8, length);
		return 1;
	}

	return 0;
}
#endif

#ifndef KERNEL_IMAGE_FLASH_OFFSET
	#define KERNEL_IMAGE_FLASH_OFFSET      0x00000000 //  0MB
#endif
#ifndef ROOTFS_IMAGE_FLASH_OFFSET
	#define ROOTFS_IMAGE_FLASH_OFFSET      0x00500000 //  5MB
#endif
#ifndef DEVICE_TREE_IMAGE_FLASH_OFFSET
	#define DEVICE_TREE_IMAGE_FLASH_OFFSET 0x00D00000 // 13MB
#endif
#ifndef EMULATOR_IMAGE_FLASH_OFFSET
	#define EMULATOR_IMAGE_FLASH_OFFSET    0x00E00000 // 14MB
#endif

void flashboot(void)
{
	unsigned int length;

#if defined(MAIN_RAM_BASE) && defined(CONFIG_CPU_TYPE_VEXRISCV) && defined(CONFIG_CPU_VARIANT_LINUX)
	unsigned int result;

	printf("Loading Image from flash...\n");
	result = copy_image_from_flash_to_ram(
		(FLASH_BOOT_ADDRESS + KERNEL_IMAGE_FLASH_OFFSET),
		(MAIN_RAM_BASE + KERNEL_IMAGE_RAM_OFFSET));


	if(result) {
		printf("Loading rootfs.cpio from flash...\n");
		result &= copy_image_from_flash_to_ram(
			(FLASH_BOOT_ADDRESS + ROOTFS_IMAGE_FLASH_OFFSET),
			(MAIN_RAM_BASE + ROOTFS_IMAGE_RAM_OFFSET));
	}

	if(result) {
		printf("Loading rv32.dtb from flash...\n");
		result &= copy_image_from_flash_to_ram(
			(FLASH_BOOT_ADDRESS + DEVICE_TREE_IMAGE_FLASH_OFFSET),
			(MAIN_RAM_BASE + DEVICE_TREE_IMAGE_RAM_OFFSET));
	}

	if(result) {
		printf("Loading emulator.bin from flash...\n");
		result &= copy_image_from_flash_to_ram(
			(FLASH_BOOT_ADDRESS + EMULATOR_IMAGE_FLASH_OFFSET),
			(MAIN_RAM_BASE + EMULATOR_IMAGE_RAM_OFFSET));
	}

	if(result) {
		boot(0, 0, 0, MAIN_RAM_BASE + EMULATOR_IMAGE_RAM_OFFSET);
		return;
	}
#endif

	printf("Booting from flash...\n");
	length = check_image_in_flash(FLASH_BOOT_ADDRESS);
	if(!length)
		return;

#ifdef MAIN_RAM_BASE
	printf("Loading %d bytes from flash...\n", length);
	// skip length and crc
	memcpy((void *)MAIN_RAM_BASE, (unsigned int *)(FLASH_BOOT_ADDRESS + 2 * sizeof(unsigned int)), length);
#endif

	boot(0, 0, 0, FIRMWARE_BASE_ADDRESS);
}
#endif

#ifdef ROM_BOOT_ADDRESS
/* When firmware is small enough, it can be interesting to run code from an
   embedded blockram memory (faster and not impacted by memory controller
   activity). Define ROM_BOOT_ADDRESS for that and initialize the blockram
   with the firmware data. */
void romboot(void)
{
	boot(0, 0, 0, ROM_BOOT_ADDRESS);
}
#endif

// SPI HARDWARE BITBANG
#ifdef CSR_SPISDCARD_BASE
#include <spisdcard.h>

void spisdcardboot(void)
{
	printf("SD Card via SPI Initialising\n");
	if(spi_sdcard_goidle() == 0) {
		printf("SD Card Timeout\n");
		return;
	}

	if(spi_sdcard_readMBR() == 0) {
		printf("SD Card MBR Timeout\n");
		return;
	}

#if defined(CONFIG_CPU_TYPE_VEXRISCV) && defined(CONFIG_CPU_VARIANT_LINUX)
	if(spi_sdcard_readFile("IMAGE","",MAIN_RAM_BASE+KERNEL_IMAGE_RAM_OFFSET)==0) return;
	if(spi_sdcard_readFile("ROOTFS~1","CPI",MAIN_RAM_BASE+ROOTFS_IMAGE_RAM_OFFSET)==0) return;
	if(spi_sdcard_readFile("RV32","DTB",MAIN_RAM_BASE+DEVICE_TREE_IMAGE_RAM_OFFSET)==0) return;
	if(spi_sdcard_readFile("EMULATOR","BIN",MAIN_RAM_BASE+EMULATOR_IMAGE_RAM_OFFSET)==0) return;

	boot(0,0,0,MAIN_RAM_BASE + EMULATOR_IMAGE_RAM_OFFSET);
#else
	if(spi_sdcard_readFile("BOOT","BIN",MAIN_RAM_BASE)==0) {
		printf("SD Card SPI boot failed\n");
		return;
	}
	boot(0, 0, 0, MAIN_RAM_BASE);
#endif
}
#endif
