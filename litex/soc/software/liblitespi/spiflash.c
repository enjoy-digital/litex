// This file is Copyright (c) 2020 Antmicro <www.antmicro.com>
// License: BSD

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <crc.h>
#include <memtest.h>

#include <generated/csr.h>
#include <generated/mem.h>
#include <system.h>

#include "spiflash.h"

#if defined(CSR_SPIFLASH_PHY_BASE) && defined(CSR_SPIFLASH_CORE_BASE)

//#define SPIFLASH_DEBUG
//#define SPIFLASH_MODULE_DUMMY_BITS 8

int spiflash_freq_init(void)
{
	unsigned int lowest_div = spiflash_phy_clk_divisor_read();
	unsigned int crc = crc32((unsigned char *)SPIFLASH_BASE, SPI_FLASH_BLOCK_SIZE);
	unsigned int crc_test = crc;

#if SPIFLASH_DEBUG
	printf("Testing against CRC32: %08x\n\r", crc);
#endif

	/* Check if block is erased (filled with 0xFF) */
	if(crc == CRC32_ERASED_FLASH) {
		printf("Block of size %d, started on address 0x%lx is erased. Cannot proceed with SPI Flash frequency test.\n\r", SPI_FLASH_BLOCK_SIZE, SPIFLASH_BASE);
		return -1;
	}

	while((crc == crc_test) && (lowest_div-- > 0)) {
		spiflash_phy_clk_divisor_write((uint32_t)lowest_div);
		crc_test = crc32((unsigned char *)SPIFLASH_BASE, SPI_FLASH_BLOCK_SIZE);
#if SPIFLASH_DEBUG
		printf("[DIV: %d] %08x\n\r", lowest_div, crc_test);
#endif
	}
	lowest_div++;
	printf("SPI Flash clk configured to %d MHz\n", (spiflash_core_sys_clk_freq_read()/(2*(1 + lowest_div)))/1000000);

	spiflash_phy_clk_divisor_write(lowest_div);

	return 0;
}

void spiflash_dummy_bits_setup(unsigned int dummy_bits)
{
	spiflash_phy_dummy_bits_write((uint32_t)dummy_bits);
#if SPIFLASH_DEBUG
	printf("Dummy bits set to: %d\n\r", spi_dummy_bits_read());
#endif
}

#ifdef CSR_SPIFLASH_CORE_MASTER_CS_ADDR

static void spiflash_master_write(uint32_t val, size_t len, size_t width, uint32_t mask)
{
	/* Be sure to empty RX queue before doing Xfer. */
	while (spiflash_core_master_status_rx_ready_read())
		spiflash_core_master_rxtx_read();

	/* Configure Master */
	spiflash_core_master_phyconfig_len_write(8 * len);
	spiflash_core_master_phyconfig_mask_write(mask);
	spiflash_core_master_phyconfig_width_write(width);

	/* Set CS. */
	spiflash_core_master_cs_write(1);

	/* Do Xfer. */
	spiflash_core_master_rxtx_write(val);
	while (!spiflash_core_master_status_rx_ready_read());

	/* Clear CS. */
	spiflash_core_master_cs_write(0);
}

#endif

void spiflash_init(void)
{
	printf("\nInitializing %s SPI Flash @0x%08lx...\n", SPIFLASH_MODULE_NAME, SPIFLASH_BASE);

#ifdef SPIFLASH_MODULE_DUMMY_BITS
	spiflash_dummy_bits_setup(SPIFLASH_MODULE_DUMMY_BITS);
#endif

#ifdef CSR_SPIFLASH_CORE_MASTER_CS_ADDR

	/* Quad / QPI Configuration. */
#ifdef SPIFLASH_MODULE_QUAD_CAPABLE
	printf("Enabling Quad mode...\n");
	spiflash_master_write(0x00000006, 1, 1, 0x1);
	spiflash_master_write(0x00014307, 3, 1, 0x1);

#ifdef SPIFLASH_MODULE_QPI_CAPABLE
	printf("Switching to QPI mode...\n");
	spiflash_master_write(0x00000035, 1, 1, 0x1);
#endif

#endif

#endif

#ifndef SPIFLASH_SKIP_FREQ_INIT
	/* Clk frequency auto-calibration. */
	spiflash_freq_init();
#else
	printf("Warning: SPI Flash frequency auto-calibration skipped, using the default divisor of %d\n", spiflash_phy_clk_divisor_read());
#endif

	memspeed((unsigned int *) SPIFLASH_BASE, SPIFLASH_SIZE/16, 1, 0);
	memspeed((unsigned int *) SPIFLASH_BASE, SPIFLASH_SIZE/16, 1, 1);
}

#endif
