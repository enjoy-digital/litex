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

#if defined(CSR_SPIFLASH_PHY_BASE) && defined(CSR_SPIFLASH_MMAP_BASE)

#define DEBUG	0
#define USER_DEFINED_DUMMY_BITS	0

static spi_mode spi_get_mode(void)
{
	return (spi_mode)spiflash_mmap_cfg_read();
}

static void spi_set_mode(spi_mode mode)
{
	spiflash_mmap_cfg_write((unsigned char)mode);
}

int spiflash_freq_init(void)
{
	unsigned int lowest_div = spiflash_phy_clk_divisor_read();
	unsigned int crc = crc32((unsigned char *)SPIFLASH_BASE, SPI_FLASH_BLOCK_SIZE);
	unsigned int crc_test = crc;

#if DEBUG
	printf("Testing against CRC32: %08x\n\r", crc);
#endif

	if(spi_get_mode() != SPI_MODE_MMAP) {
		spi_set_mode(SPI_MODE_MMAP);
	}

	/* Check if block is erased (filled with 0xFF) */
	if(crc == CRC32_ERASED_FLASH) {
		printf("Block of size %d, started on address 0x%lx is erased. Cannot proceed with SPI frequency test.\n\r", SPI_FLASH_BLOCK_SIZE, SPIFLASH_BASE);
		return -1;
	}

	for(int i = lowest_div; (crc == crc_test) && (i >= 0); i--) {
		lowest_div = i;
		spiflash_phy_clk_divisor_write((uint32_t)i);
		crc_test = crc32((unsigned char *)SPIFLASH_BASE, SPI_FLASH_BLOCK_SIZE);
#if DEBUG
		printf("[DIV: %d] %08x\n\r", i, crc_test);
#endif
	}
	lowest_div++;
	printf("SPIFlash freq configured to %d MHz\n", (spiflash_mmap_sys_clk_freq_read()/(2*(1 + lowest_div)))/1000000);

	spiflash_phy_clk_divisor_write(lowest_div);

	return 0;
}

void spiflash_dummy_bits_setup(unsigned int dummy_bits)
{
	spiflash_phy_dummy_bits_write((uint32_t)dummy_bits);
#if DEBUG
	printf("Dummy bits set to: %d\n\r", spi_dummy_bits_read());
#endif
}

void spiflash_init(void)
{
	int ret;

	printf("Initializing SPIFlash...\n");

	ret = spiflash_freq_init();
	if (ret < 0)
		return;
#if (USER_DEFINED_DUMMY_BITS > 0)
	spiflash_dummy_bits_setup(USER_DEFINED_DUMMY_BITS);
#endif
}

#endif
