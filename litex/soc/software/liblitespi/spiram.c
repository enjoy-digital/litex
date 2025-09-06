// Copyright (c) 2020 Antmicro <www.antmicro.com>
// Copyright (c) 2024 Fin Maaß <f.maass@vogl-electronic.com>
// License: BSD

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libbase/memtest.h>

#include <generated/csr.h>
#include <generated/mem.h>
#include <generated/soc.h>
#include <system.h>

#include "spiram.h"

//#define SPIRAM_DEBUG

#if defined(CSR_SPIRAM_BASE)

int spiram_freq_init(void)
{

#ifdef CSR_SPIRAM_PHY_CLK_DIVISOR_ADDR

	int data_errors = 0;
	unsigned int lowest_div;

	lowest_div = spiram_phy_clk_divisor_read();

	invd_cpu_dcache_range((void *)SPIRAM_BASE, SPIRAM_BLOCK_SIZE);
	flush_l2_cache();

	while((data_errors == 0) && (lowest_div-- > 0)) {
		spiram_phy_clk_divisor_write((uint32_t)lowest_div);
		invd_cpu_dcache_range((void *)SPIRAM_BASE, SPIRAM_BLOCK_SIZE);
		flush_l2_cache();
		data_errors = memtest_data((unsigned int *) SPIRAM_BASE, min(SPIRAM_SIZE, MEMTEST_DATA_SIZE), 1, NULL);
#ifdef SPIRAM_DEBUG
		printf("[DIV: %d]\n\r", lowest_div);
#endif
	}
	lowest_div++;
	printf("SPI RAM clk configured to %d MHz\n", CONFIG_CLOCK_FREQUENCY/(2*(1+lowest_div)*1000000));

	spiram_phy_clk_divisor_write(lowest_div);

#else

	printf("SPI RAM clk configured to %ld MHz\n", SPIRAM_PHY_FREQUENCY/1000000);

#endif

	return 0;
}

void spiram_dummy_bits_setup(unsigned int dummy_bits)
{
	spiram_mmap_dummy_bits_write((uint32_t)dummy_bits);
#ifdef SPIRAM_DEBUG
	printf("Dummy bits set to: %" PRIx32 "\n\r", spiram_mmap_dummy_bits_read());
#endif
}

#ifdef CSR_SPIRAM_MASTER_CS_ADDR

static void spiram_len_mask_width_write(uint32_t len, uint32_t width, uint32_t mask)
{
	uint32_t tmp = len & ((1 <<  CSR_SPIRAM_MASTER_PHYCONFIG_LEN_SIZE) - 1);
	uint32_t word = tmp << CSR_SPIRAM_MASTER_PHYCONFIG_LEN_OFFSET;
	tmp = width & ((1 << CSR_SPIRAM_MASTER_PHYCONFIG_WIDTH_SIZE) - 1);
	word |= tmp << CSR_SPIRAM_MASTER_PHYCONFIG_WIDTH_OFFSET;
	tmp = mask & ((1 <<  CSR_SPIRAM_MASTER_PHYCONFIG_MASK_SIZE) - 1);
	word |= tmp << CSR_SPIRAM_MASTER_PHYCONFIG_MASK_OFFSET;
	spiram_master_phyconfig_write(word);
}

static bool spiram_rx_ready(void)
{
	return (spiram_master_status_read() >> CSR_SPIRAM_MASTER_STATUS_RX_READY_OFFSET) & 1;
}

static void spiram_master_write(uint32_t val, size_t len, size_t width, uint32_t mask)
{
	/* Be sure to empty RX queue before doing Xfer. */
	while (spiram_rx_ready())
		spiram_master_rxtx_read();

	/* Configure Master */
	spiram_len_mask_width_write(8*len, width, mask);

	/* Set CS. */
	spiram_master_cs_write(1);

	/* Do Xfer. */
	spiram_master_rxtx_write(val);
	while (!spiram_rx_ready());

	/* Clear RX queue. */
	spiram_master_rxtx_read();

	/* Clear CS. */
	spiram_master_cs_write(0);
}

#endif

void spiram_memspeed(void) {
	/* Test Sequential Read accesses */
	memspeed((unsigned int *) SPIRAM_BASE, 4096, 1, 0);

	/* Test Random Read accesses */
	memspeed((unsigned int *) SPIRAM_BASE, 4096, 1, 1);
}

void spiram_init(void)
{
	printf("\nInitializing %s SPI RAM @0x%08lx...\n", SPIRAM_MODULE_NAME, SPIRAM_BASE);

#ifdef SPIRAM_MODULE_DUMMY_BITS
	spiram_dummy_bits_setup(SPIRAM_MODULE_DUMMY_BITS);
#endif

#ifdef CSR_SPIRAM_MASTER_CS_ADDR

	/* Quad / QPI Configuration. */
#ifdef SPIRAM_MODULE_QUAD_CAPABLE
	printf("Enabling Quad mode...\n");
	spiram_master_write(0x00000006, 1, 1, 0x1);
	spiram_master_write(0x00014307, 3, 1, 0x1);
#endif

#ifdef SPIRAM_MODULE_QPI_CAPABLE
	printf("Switching to QPI mode...\n");
	spiram_master_write(0x00000035, 1, 1, 0x1);
#endif

#endif

#ifndef SPIRAM_SKIP_FREQ_INIT
	/* Clk frequency auto-calibration. */
	spiram_freq_init();
#endif

	/* Test SPI RAM speed */
	spiram_memspeed();
}

#endif
