// This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
// This file is Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
// This file is Copyright (c) 2015 Yann Sionneau <ys@m-labs.hk>
// This file is Copyright (c) 2015 whitequark <whitequark@whitequark.org>
// This file is Copyright (c) 2019 Ambroz Bizjak <ambrop7@gmail.com>
// This file is Copyright (c) 2019 Caleb Jamison <cbjamo@gmail.com>
// This file is Copyright (c) 2018 Dolu1990 <charles.papon.90@gmail.com>
// This file is Copyright (c) 2018 Felix Held <felix-github@felixheld.de>
// This file is Copyright (c) 2019 Gabriel L. Somlo <gsomlo@gmail.com>
// This file is Copyright (c) 2018 Jean-François Nguyen <jf@lambdaconcept.fr>
// This file is Copyright (c) 2018 Sergiusz Bazanski <q3k@q3k.org>
// This file is Copyright (c) 2016 Tim 'mithro' Ansell <mithro@mithis.com>

// License: BSD

#include <stdio.h>
#include <stdlib.h>
#include <console.h>
#include <string.h>
#include <uart.h>
#include <system.h>
#include <id.h>
#include <irq.h>
#include <crc.h>

#include <generated/csr.h>
#include <generated/mem.h>
#include <generated/git.h>

#ifdef CSR_ETHMAC_BASE
#include <net/microudp.h>
#endif

#ifdef CSR_SPIFLASH_BASE
#include <spiflash.h>
#endif

#ifdef CSR_ETHPHY_MDIO_W_ADDR
#include <mdio.h>
#endif

#include "sdram.h"
#include "boot.h"

/* General address space functions */

#define NUMBER_OF_BYTES_ON_A_LINE 16
static void dump_bytes(unsigned int *ptr, int count, unsigned long addr)
{
	char *data = (char *)ptr;
	int line_bytes = 0, i = 0;

	putsnonl("Memory dump:");
	while(count > 0){
		line_bytes =
			(count > NUMBER_OF_BYTES_ON_A_LINE)?
				NUMBER_OF_BYTES_ON_A_LINE : count;

		printf("\n0x%08x  ", addr);
		for(i=0;i<line_bytes;i++)
			printf("%02x ", *(unsigned char *)(data+i));

		for(;i<NUMBER_OF_BYTES_ON_A_LINE;i++)
			printf("   ");

		printf(" ");

		for(i=0;i<line_bytes;i++) {
			if((*(data+i) < 0x20) || (*(data+i) > 0x7e))
				printf(".");
			else
				printf("%c", *(data+i));
		}

		for(;i<NUMBER_OF_BYTES_ON_A_LINE;i++)
			printf(" ");

		data += (char)line_bytes;
		count -= line_bytes;
		addr += line_bytes;
	}
	printf("\n");
}

static void mr(char *startaddr, char *len)
{
	char *c;
	unsigned int *addr;
	unsigned int length;

	if(*startaddr == 0) {
		printf("mr <address> [length]\n");
		return;
	}
	addr = (unsigned *)strtoul(startaddr, &c, 0);
	if(*c != 0) {
		printf("incorrect address\n");
		return;
	}
	if(*len == 0) {
		length = 4;
	} else {
		length = strtoul(len, &c, 0);
		if(*c != 0) {
			printf("incorrect length\n");
			return;
		}
	}

	dump_bytes(addr, length, (unsigned long)addr);
}

static void mw(char *addr, char *value, char *count)
{
	char *c;
	unsigned int *addr2;
	unsigned int value2;
	unsigned int count2;
	unsigned int i;

	if((*addr == 0) || (*value == 0)) {
		printf("mw <address> <value> [count]\n");
		return;
	}
	addr2 = (unsigned int *)strtoul(addr, &c, 0);
	if(*c != 0) {
		printf("incorrect address\n");
		return;
	}
	value2 = strtoul(value, &c, 0);
	if(*c != 0) {
		printf("incorrect value\n");
		return;
	}
	if(*count == 0) {
		count2 = 1;
	} else {
		count2 = strtoul(count, &c, 0);
		if(*c != 0) {
			printf("incorrect count\n");
			return;
		}
	}
	for (i=0;i<count2;i++) *addr2++ = value2;
}

static void mc(char *dstaddr, char *srcaddr, char *count)
{
	char *c;
	unsigned int *dstaddr2;
	unsigned int *srcaddr2;
	unsigned int count2;
	unsigned int i;

	if((*dstaddr == 0) || (*srcaddr == 0)) {
		printf("mc <dst> <src> [count]\n");
		return;
	}
	dstaddr2 = (unsigned int *)strtoul(dstaddr, &c, 0);
	if(*c != 0) {
		printf("incorrect destination address\n");
		return;
	}
	srcaddr2 = (unsigned int *)strtoul(srcaddr, &c, 0);
	if(*c != 0) {
		printf("incorrect source address\n");
		return;
	}
	if(*count == 0) {
		count2 = 1;
	} else {
		count2 = strtoul(count, &c, 0);
		if(*c != 0) {
			printf("incorrect count\n");
			return;
		}
	}
	for (i=0;i<count2;i++) *dstaddr2++ = *srcaddr2++;
}

#if (defined CSR_SPIFLASH_BASE && defined SPIFLASH_PAGE_SIZE)
static void fw(char *addr, char *value, char *count)
{
	char *c;
	unsigned int addr2;
	unsigned int value2;
	unsigned int count2;
	unsigned int i;

	if((*addr == 0) || (*value == 0)) {
		printf("fw <offset> <value> [count]\n");
		return;
	}
	addr2 = strtoul(addr, &c, 0);
	if(*c != 0) {
		printf("incorrect offset\n");
		return;
	}
	value2 = strtoul(value, &c, 0);
	if(*c != 0) {
		printf("incorrect value\n");
		return;
	}
	if(*count == 0) {
		count2 = 1;
	} else {
		count2 = strtoul(count, &c, 0);
		if(*c != 0) {
			printf("incorrect count\n");
			return;
		}
	}
	for (i=0;i<count2;i++) write_to_flash(addr2 + i * 4, (unsigned char *)&value2, 4);
}
#endif

#ifdef CSR_ETHPHY_MDIO_W_ADDR
static void mdiow(char *phyadr, char *reg, char *val)
{
	char *c;
	unsigned int phyadr2;
	unsigned int reg2;
	unsigned int val2;

	if((*phyadr == 0) || (*reg == 0) || (*val == 0)) {
		printf("mdiow <phyadr> <reg> <value>\n");
		return;
	}
	phyadr2 = strtoul(phyadr, &c, 0);
	if(*c != 0) {
		printf("incorrect phyadr\n");
		return;
	}
	reg2 = strtoul(reg, &c, 0);
	if(*c != 0) {
		printf("incorrect reg\n");
		return;
	}
	val2 = strtoul(val, &c, 0);
	if(*c != 0) {
		printf("incorrect val\n");
		return;
	}
	mdio_write(phyadr2, reg2, val2);
}

static void mdior(char *phyadr, char *reg)
{
	char *c;
	unsigned int phyadr2;
	unsigned int reg2;
	unsigned int val;

	if((*phyadr == 0) || (*reg == 0)) {
		printf("mdior <phyadr> <reg>\n");
		return;
	}
	phyadr2 = strtoul(phyadr, &c, 0);
	if(*c != 0) {
		printf("incorrect phyadr\n");
		return;
	}
	reg2 = strtoul(reg, &c, 0);
	if(*c != 0) {
		printf("incorrect reg\n");
		return;
	}
	val = mdio_read(phyadr2, reg2);
	printf("reg %d: 0x%04x\n", reg2, val);
}

static void mdiod(char *phyadr, char *count)
{
	char *c;
	unsigned int phyadr2;
	unsigned int count2;
	unsigned int val;
	int i;

	if((*phyadr == 0) || (*count == 0)) {
		printf("mdiod <phyadr> <count>\n");
		return;
	}
	phyadr2 = strtoul(phyadr, &c, 0);
	if(*c != 0) {
		printf("incorrect phyadr\n");
		return;
	}
	count2 = strtoul(count, &c, 0);
	if(*c != 0) {
		printf("incorrect count\n");
		return;
	}
	printf("MDIO dump @0x%x:\n", phyadr2);
	for (i=0; i<count2; i++) {
		val = mdio_read(phyadr2, i);
		printf("reg %d: 0x%04x\n", i, val);
	}
}
#endif

static void crc(char *startaddr, char *len)
{
	char *c;
	char *addr;
	unsigned int length;

	if((*startaddr == 0)||(*len == 0)) {
		printf("crc <address> <length>\n");
		return;
	}
	addr = (char *)strtoul(startaddr, &c, 0);
	if(*c != 0) {
		printf("incorrect address\n");
		return;
	}
	length = strtoul(len, &c, 0);
	if(*c != 0) {
		printf("incorrect length\n");
		return;
	}

	printf("CRC32: %08x\n", crc32((unsigned char *)addr, length));
}

static void ident(void)
{
	char buffer[IDENT_SIZE];

	get_ident(buffer);
	printf("Ident: %s\n", buffer);
}

/* Init + command line */

static void help(void)
{
	puts("LiteX BIOS, available commands:");
	puts("mr         - read address space");
	puts("mw         - write address space");
	puts("mc         - copy address space");
#if (defined CSR_SPIFLASH_BASE && defined SPIFLASH_PAGE_SIZE)
	puts("fw         - write to flash");
#endif
#ifdef CSR_ETHPHY_MDIO_W_ADDR
	puts("mdiow      - write MDIO register");
	puts("mdior      - read MDIO register");
	puts("mdiod      - dump MDIO registers");
#endif
	puts("");
	puts("crc        - compute CRC32 of a part of the address space");
	puts("ident      - display identifier");
	puts("");
#ifdef CSR_CTRL_BASE
	puts("reboot     - reset processor");
#endif
#ifdef CSR_ETHMAC_BASE
	puts("netboot    - boot via TFTP");
#endif
	puts("serialboot - boot via SFL");
#ifdef FLASH_BOOT_ADDRESS
	puts("flashboot  - boot from flash");
#endif
#ifdef ROM_BOOT_ADDRESS
	puts("romboot    - boot from embedded rom");
#endif
	puts("");
#ifdef CSR_SDRAM_BASE
	puts("memtest    - run a memory test");
#endif
}

static char *get_token(char **str)
{
	char *c, *d;

	c = (char *)strchr(*str, ' ');
	if(c == NULL) {
		d = *str;
		*str = *str+strlen(*str);
		return d;
	}
	*c = 0;
	d = *str;
	*str = c+1;
	return d;
}

#ifdef CSR_CTRL_BASE
static void reboot(void)
{
	ctrl_reset_write(1);
}
#endif

static void do_command(char *c)
{
	char *token;

	token = get_token(&c);

	if(strcmp(token, "mr") == 0) mr(get_token(&c), get_token(&c));
	else if(strcmp(token, "mw") == 0) mw(get_token(&c), get_token(&c), get_token(&c));
	else if(strcmp(token, "mc") == 0) mc(get_token(&c), get_token(&c), get_token(&c));
#if (defined CSR_SPIFLASH_BASE && defined SPIFLASH_PAGE_SIZE)
	else if(strcmp(token, "fw") == 0) fw(get_token(&c), get_token(&c), get_token(&c));
#endif
#ifdef CSR_ETHPHY_MDIO_W_ADDR
	else if(strcmp(token, "mdiow") == 0) mdiow(get_token(&c), get_token(&c), get_token(&c));
	else if(strcmp(token, "mdior") == 0) mdior(get_token(&c), get_token(&c));
	else if(strcmp(token, "mdiod") == 0) mdiod(get_token(&c), get_token(&c));
#endif
	else if(strcmp(token, "crc") == 0) crc(get_token(&c), get_token(&c));
	else if(strcmp(token, "ident") == 0) ident();

#ifdef CONFIG_L2_SIZE
	else if(strcmp(token, "flushl2") == 0) flush_l2_cache();
#endif
#ifdef CSR_CTRL_BASE
	else if(strcmp(token, "reboot") == 0) reboot();
#endif
#ifdef FLASH_BOOT_ADDRESS
	else if(strcmp(token, "flashboot") == 0) flashboot();
#endif
#ifdef ROM_BOOT_ADDRESS
	else if(strcmp(token, "romboot") == 0) romboot();
#endif
	else if(strcmp(token, "serialboot") == 0) serialboot();
#ifdef CSR_ETHMAC_BASE
	else if(strcmp(token, "netboot") == 0) netboot();
#endif

	else if(strcmp(token, "help") == 0) help();

#ifdef CSR_SDRAM_BASE
	else if(strcmp(token, "sdrrow") == 0) sdrrow(get_token(&c));
	else if(strcmp(token, "sdrsw") == 0) sdrsw();
	else if(strcmp(token, "sdrhw") == 0) sdrhw();
	else if(strcmp(token, "sdrrdbuf") == 0) sdrrdbuf(-1);
	else if(strcmp(token, "sdrrd") == 0) sdrrd(get_token(&c), get_token(&c));
	else if(strcmp(token, "sdrrderr") == 0) sdrrderr(get_token(&c));
	else if(strcmp(token, "sdrwr") == 0) sdrwr(get_token(&c));
#ifdef CSR_DDRPHY_BASE
	else if(strcmp(token, "sdrinit") == 0) sdrinit();
#ifdef CSR_DDRPHY_WLEVEL_EN_ADDR
	else if(strcmp(token, "sdrwlon") == 0) sdrwlon();
	else if(strcmp(token, "sdrwloff") == 0) sdrwloff();
#endif
	else if(strcmp(token, "sdrlevel") == 0) sdrlevel();
#endif
	else if(strcmp(token, "memtest") == 0) memtest();
#endif

	else if(strcmp(token, "") != 0)
		printf("Command not found\n");
}

extern unsigned int _ftext, _edata;

static void crcbios(void)
{
	unsigned long offset_bios;
	unsigned long length;
	unsigned int expected_crc;
	unsigned int actual_crc;

	/*
	 * _edata is located right after the end of the flat
	 * binary image. The CRC tool writes the 32-bit CRC here.
	 * We also use the address of _edata to know the length
	 * of our code.
	 */
	offset_bios = (unsigned long)&_ftext;
	expected_crc = _edata;
	length = (unsigned long)&_edata - offset_bios;
	actual_crc = crc32((unsigned char *)offset_bios, length);
	if(expected_crc == actual_crc)
		printf(" BIOS CRC passed (%08x)\n", actual_crc);
	else {
		printf(" BIOS CRC failed (expected %08x, got %08x)\n", expected_crc, actual_crc);
		printf(" The system will continue, but expect problems.\n");
	}
}

static void readstr(char *s, int size)
{
	static char skip = 0;
	char c[2];
	int ptr;

	c[1] = 0;
	ptr = 0;
	while(1) {
		c[0] = readchar();
		if (c[0] == skip)
			continue;
		skip = 0;
		switch(c[0]) {
			case 0x7f:
			case 0x08:
				if(ptr > 0) {
					ptr--;
					putsnonl("\x08 \x08");
				}
				break;
			case 0x07:
				break;
			case '\r':
				skip = '\n';
				s[ptr] = 0x00;
				putsnonl("\n");
				return;
			case '\n':
				skip = '\r';
				s[ptr] = 0x00;
				putsnonl("\n");
				return;
			default:
				putsnonl(c);
				s[ptr] = c[0];
				ptr++;
				break;
		}
	}
}

static void boot_sequence(void)
{
	if(serialboot()) {
#ifdef FLASH_BOOT_ADDRESS
		flashboot();
#endif
#ifdef ROM_BOOT_ADDRESS
		romboot();
#endif
#ifdef CSR_ETHMAC_BASE
#ifdef CSR_ETHPHY_MODE_DETECTION_MODE_ADDR
		eth_mode();
#endif
		netboot();
#endif
		printf("No boot medium found\n");
	}
}

int main(int i, char **c)
{
	char buffer[64];
	int sdr_ok;

	irq_setmask(0);
	irq_setie(1);
	uart_init();

	printf("\n");
	printf("\e[1m        __   _ __      _  __\e[0m\n");
	printf("\e[1m       / /  (_) /____ | |/_/\e[0m\n");
	printf("\e[1m      / /__/ / __/ -_)>  <\e[0m\n");
	printf("\e[1m     /____/_/\\__/\\__/_/|_|\e[0m\n");
	printf("\n");
	printf(" (c) Copyright 2012-2019 Enjoy-Digital\n");
	printf("\n");
	printf(" BIOS built on "__DATE__" "__TIME__"\n");
	crcbios();
	printf("\n");
	printf(" Migen git sha1: "MIGEN_GIT_SHA1"\n");
	printf(" LiteX git sha1: "LITEX_GIT_SHA1"\n");
	printf("\n");
	printf("--=============== \e[1mSoC\e[0m ==================--\n");
	printf("\e[1mCPU\e[0m:       ");
#ifdef __lm32__
	printf("LM32");
#elif __or1k__
	printf("MOR1KX");
#elif __picorv32__
	printf("PicoRV32");
#elif __vexriscv__
	printf("VexRiscv");
#elif __minerva__
	printf("Minerva");
#elif __rocket__
	printf("RocketRV64[imac]");
#else
	printf("Unknown");
#endif
	printf(" @ %dMHz\n", CONFIG_CLOCK_FREQUENCY/1000000);
	printf("\e[1mROM\e[0m:       %dKB\n", ROM_SIZE/1024);
	printf("\e[1mSRAM\e[0m:      %dKB\n", SRAM_SIZE/1024);
#ifdef CONFIG_L2_SIZE
	printf("\e[1mL2\e[0m:        %dKB\n", CONFIG_L2_SIZE/1024);
#endif
#ifdef MAIN_RAM_SIZE
	printf("\e[1mMAIN-RAM\e[0m:  %dKB\n", MAIN_RAM_SIZE/1024);
#endif
	printf("\n");

	sdr_ok = 1;
#if defined(CSR_ETHMAC_BASE) || defined(CSR_SDRAM_BASE)
	printf("--========== \e[1mInitialization\e[0m ============--\n");
#ifdef CSR_ETHMAC_BASE
	eth_init();
#endif
#ifdef CSR_SDRAM_BASE
	sdr_ok = sdrinit();
#else
#ifdef MAIN_RAM_TEST
	sdr_ok = memtest();
#endif
#endif
	if (sdr_ok !=1)
		printf("Memory initialization failed\n");
	printf("\n");
#endif

	if(sdr_ok) {
		printf("--============== \e[1mBoot\e[0m ==================--\n");
		boot_sequence();
		printf("\n");
	}

	printf("--============= \e[1mConsole\e[0m ================--\n");
	while(1) {
		putsnonl("\e[92;1mlitex\e[0m> ");
		readstr(buffer, 64);
		do_command(buffer);
	}
	return 0;
}
