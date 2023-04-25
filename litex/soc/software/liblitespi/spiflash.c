// This file is Copyright (c) 2020 Antmicro <www.antmicro.com>
// License: BSD

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libbase/memtest.h>
#include <libbase/crc.h>

#include <generated/csr.h>
#include <generated/mem.h>
#include <system.h>

#include "spiflash.h"

//#define SPIFLASH_DEBUG

#if defined(CSR_SPIFLASH_CORE_BASE)

int spiflash_freq_init(void)
{

#ifdef CSR_SPIFLASH_PHY_CLK_DIVISOR_ADDR

	unsigned int lowest_div, crc, crc_test;

	lowest_div = spiflash_phy_clk_divisor_read();
	crc        = crc32((unsigned char *)SPIFLASH_BASE, SPI_FLASH_BLOCK_SIZE);
	crc_test   = crc;

#if SPIFLASH_DEBUG
	printf("Testing against CRC32: %08x\n\r", crc);
#endif

	/* Check if block is erased (filled with 0xFF) */
	if(crc == CRC32_ERASED_FLASH) {
		printf("First SPI Flash block erased, unable to perform freq test.\n\r");
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
	printf("SPI Flash clk configured to %d MHz\n", (SPIFLASH_PHY_FREQUENCY/(2*(1 + lowest_div)))/1000000);

	spiflash_phy_clk_divisor_write(lowest_div);

#else

	printf("SPI Flash clk configured to %ld MHz\n", (unsigned long)(SPIFLASH_PHY_FREQUENCY/1e6));

#endif

	return 0;
}

void spiflash_dummy_bits_setup(unsigned int dummy_bits)
{
	spiflash_core_mmap_dummy_bits_write((uint32_t)dummy_bits);
#if SPIFLASH_DEBUG
	printf("Dummy bits set to: %d\n\r", spiflash_core_mmap_dummy_bits_read());
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

static volatile uint8_t w_buf[SPI_FLASH_BLOCK_SIZE + 4];
static volatile uint8_t r_buf[SPI_FLASH_BLOCK_SIZE + 4];

static uint32_t transfer_byte(uint8_t b)
{
	/* wait for tx ready */
	while (!spiflash_core_master_status_tx_ready_read());

	spiflash_core_master_rxtx_write((uint32_t)b);

	/* wait for rx ready */
	while (!spiflash_core_master_status_rx_ready_read());

	return spiflash_core_master_rxtx_read();
}

static void transfer_cmd(uint8_t *bs, uint8_t *resp, int len)
{
	spiflash_core_master_phyconfig_len_write(8);
	spiflash_core_master_phyconfig_width_write(1);
	spiflash_core_master_phyconfig_mask_write(1);
	spiflash_core_master_cs_write(1);

	flush_cpu_dcache();
	for (int i=0; i < len; i++) {
		resp[i] = transfer_byte(bs[i]);
	}

	spiflash_core_master_cs_write(0);
	flush_cpu_dcache();
}

static uint32_t spiflash_read_status_register(void)
{
	volatile uint8_t buf[4];
	w_buf[0] = 0x05;
	w_buf[1] = 0x00;
	transfer_cmd(w_buf, buf, 4);

#if SPIFLASH_DEBUG
	printf("[SR: %02x %02x %02x %02x]", buf[0], buf[1], buf[2], buf[3]);
#endif

	/* FIXME normally the status should be in buf[1],
	   but we have to read it a few more times to be
	   stable for unknown reasons */
	return buf[3];
}

static void spiflash_write_enable(void)
{
	uint8_t buf[1];
	w_buf[0] = 0x06;
	transfer_cmd(w_buf, buf, 1);
}

static void page_program(uint32_t addr, uint8_t *data, int len)
{
	w_buf[0] = 0x02;
	w_buf[1] = addr>>16;
	w_buf[2] = addr>>8;
	w_buf[3] = addr>>0;
	memcpy(w_buf+4, data, len);
	transfer_cmd(w_buf, r_buf, len+4);
}

static void spiflash_sector_erase(uint32_t addr)
{
	w_buf[0] = 0xd8;
	w_buf[1] = addr>>16;
	w_buf[2] = addr>>8;
	w_buf[3] = addr>>0;
	transfer_cmd(w_buf, r_buf, 4);
}

/* erase page size in bytes, check flash datasheet */
#define SPI_FLASH_ERASE_SIZE (64*1024)

#define min(x, y) (((x) < (y)) ? (x) : (y))

void spiflash_erase_range(uint32_t addr, uint32_t len)
{
	uint32_t i = 0;
	uint32_t j = 0;
	for (i=0; i<len; i+=SPI_FLASH_ERASE_SIZE) {
		printf("Erase SPI Flash @0x%08lx", ((uint32_t)addr+i));
		spiflash_write_enable();
		spiflash_sector_erase(addr+i);

		while (spiflash_read_status_register() & 1) {
			printf(".");
			cdelay(CONFIG_CLOCK_FREQUENCY/25);
		}
		printf("\n");

		/* check if region was really erased */
		for (j = 0; j < SPI_FLASH_ERASE_SIZE; j++) {
			uint8_t* peek = (((uint8_t*)SPIFLASH_BASE)+addr+i+j);
			if (*peek != 0xff) {
				printf("Error: location 0x%08lx not erased (%0x2x)\n", addr+i+j, *peek);
			}
		}
	}
}

int spiflash_write_stream(uint32_t addr, uint8_t *stream, uint32_t len)
{
	int res = 0;
	uint32_t w_len = min(len, SPI_FLASH_BLOCK_SIZE);
	uint32_t offset = 0;
	uint32_t j = 0;

#if SPIFLASH_DEBUG
	printf("Write SPI Flash @0x%08lx", ((uint32_t)addr));
#endif

	while(w_len) {
		spiflash_write_enable();
		page_program(addr+offset, stream+offset, w_len);

		while(spiflash_read_status_register() & 1) {
#if SPIFLASH_DEBUG
			printf(".");
#endif
		}

		for (j = 0; j < w_len; j++) {
			uint8_t* peek = (((uint8_t*)SPIFLASH_BASE)+addr+offset+j);
			if (*peek != stream[offset+j]) {
				printf("Error: verify failed at 0x%08lx (0x%02x should be 0x%02x)\n", (uint32_t)peek, *peek, stream[offset+j]);
			}
		}

		offset += w_len;
		w_len = min(len-offset, SPI_FLASH_BLOCK_SIZE);
		res = offset;
	}
#if SPIFLASH_DEBUG
  printf("\n");
#endif
	return res;
}

#endif

void spiflash_memspeed(void) {
	/* Test Sequential Read accesses */
	memspeed((unsigned int *) SPIFLASH_BASE, 4096, 1, 0);

	/* Test Random Read accesses */
	memspeed((unsigned int *) SPIFLASH_BASE, 4096, 1, 1);
}

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
#endif

	/* Test SPI Flash speed */
	spiflash_memspeed();
}

#endif
