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

#if defined(CSR_SPIFLASH_PHY_BASE) && defined(CSR_SPIFLASH_CORE_BASE)

#define DEBUG	0
#define USER_DEFINED_DUMMY_BITS	0

int spiflash_freq_init(void)
{
	unsigned int lowest_div = spiflash_phy_clk_divisor_read();
	unsigned int crc = crc32((unsigned char *)SPIFLASH_BASE, SPI_FLASH_BLOCK_SIZE);
	unsigned int crc_test = crc;

#if DEBUG
	printf("Testing against CRC32: %08x\n\r", crc);
#endif

	/* Check if block is erased (filled with 0xFF) */
	if(crc == CRC32_ERASED_FLASH) {
		printf("Block of size %d, started on address 0x%lx is erased. Cannot proceed with SPI frequency test.\n\r", SPI_FLASH_BLOCK_SIZE, SPIFLASH_BASE);
		return -1;
	}

	while((crc == crc_test) && (lowest_div-- > 0)) {
		spiflash_phy_clk_divisor_write((uint32_t)lowest_div);
		crc_test = crc32((unsigned char *)SPIFLASH_BASE, SPI_FLASH_BLOCK_SIZE);
#if DEBUG
		printf("[DIV: %d] %08x\n\r", lowest_div, crc_test);
#endif
	}
	lowest_div++;
	printf("SPIFlash freq configured to %d MHz\n", (spiflash_core_sys_clk_freq_read()/(2*(1 + lowest_div)))/1000000);

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

static void spiflash_master_write(uint32_t val, size_t len, size_t width, uint32_t mask)
{
	/* empty rx queue */
	while (spiflash_mmap_master_status_rx_ready_read())
		spiflash_mmap_master_rxtx_read();

	spiflash_mmap_master_cs_write(1);
	spiflash_mmap_master_phyconfig_len_write(8 * len);
	spiflash_mmap_master_phyconfig_mask_write(mask);
	spiflash_mmap_master_phyconfig_width_write(width);
	spiflash_mmap_master_rxtx_write(val);

	while (!spiflash_mmap_master_status_rx_ready_read());
	spiflash_mmap_master_cs_write(0);
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

#ifdef FLASH_CHIP_MX25L12833F_QUAD
	/* enable write enable latch */
	printf("Enabling quad lines on MX25L12833F...\n");
	spiflash_master_write(0x00000006, 1, 1, 0x1);

	/* enable quad lines */
	spiflash_master_write(0x00014307, 3, 1, 0x1);

#ifdef FLASH_CHIP_MX25L12833F_QPI
	/* enter qpi */
	printf("Entering QPI mode...\n");
	spiflash_master_write(0x00000035, 1, 1, 0x1);
#endif

#endif /* FLASH_CHIP_MX25L12833F_QUAD */
}

#endif
