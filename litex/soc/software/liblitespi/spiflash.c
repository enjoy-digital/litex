// This file is Copyright (c) 2020 Antmicro <www.antmicro.com>
// License: BSD

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <crc.h>

#include <generated/csr.h>
#include <generated/mem.h>
#include <system.h>

#include "spiflash.h"

#ifdef SPIXIP_BASE

#define DEBUG	0
#define USER_DEFINED_DUMMY_BITS	0

static spi_mode spi_get_mode(void)
{
	return (spi_mode)spi_cfg_read();
}

static void spi_set_mode(spi_mode mode)
{
	spi_cfg_write((unsigned char)mode);
}

int spi_frequency_test(void)
{
	unsigned int lowest_div = spi_clk_divisor_read();
	unsigned int crc = crc32((unsigned char *)SPIXIP_BASE, SPI_FLASH_BLOCK_SIZE);
	unsigned int crc_test = crc;

#if DEBUG
	printf("Testing against CRC32: %08x\n\r", crc);
#endif

	if(spi_get_mode() != SPI_MODE_MMAP) {
		spi_set_mode(SPI_MODE_MMAP);
	}

	/* Check if block is erased (filled with 0xFF) */
	if(crc == CRC32_ERASED_FLASH) {
		printf("Block of size %d, started on address 0x%x is erased. Cannot proceed with SPI frequency test.\n\r", SPI_FLASH_BLOCK_SIZE, SPIXIP_BASE);
		return -1;
	}

	for(int i = lowest_div; (crc == crc_test) && (i >= 0); i--) {
		lowest_div = i;
		spi_clk_divisor_write((uint32_t)i);
		crc_test = crc32((unsigned char *)SPIXIP_BASE, SPI_FLASH_BLOCK_SIZE);
#if DEBUG
		printf("[DIV: %d] %08x\n\r", i, crc_test);
#endif
	}
	lowest_div++;
	printf("Maximum available frequency: %d Hz\n\r", (spi_sys_clk_freq_read()/(2*(1 + lowest_div))));

	return lowest_div;
}

#endif

void spi_dummy_bits_setup(unsigned int dummy_bits)
{
	spi_dummy_bits_write((uint32_t)dummy_bits);
#if DEBUG
	printf("Dummy bits set to: %d\n\r", spi_dummy_bits_read());
#endif
}

void spi_autoconfig(void)
{
	int ret = spi_frequency_test();
	if(ret < 0) {
		return;
	} else {
		spi_clk_divisor_write((uint32_t)ret);
	}
#if (USER_DEFINED_DUMMY_BITS > 0)
	spi_dummy_bits_setup(USER_DEFINED_DUMMY_BITS);
#endif
}

