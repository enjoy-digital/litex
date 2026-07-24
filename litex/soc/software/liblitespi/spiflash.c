// This file is Copyright (c) 2020 Antmicro <www.antmicro.com>
// License: BSD

#include <inttypes.h>
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

#if defined(CSR_SPIFLASH_BASE)

int spiflash_freq_init(void)
{

#ifdef CSR_SPIFLASH_PHY_CLK_DIVISOR_ADDR

	unsigned int lowest_div;
#ifdef SPIFLASH_BASE
	unsigned int crc, crc_test;
#endif

	lowest_div = spiflash_phy_clk_divisor_read();

#ifdef SPIFLASH_BASE
	invd_cpu_dcache_range((void *)SPIFLASH_BASE, SPI_FLASH_BLOCK_SIZE);
	flush_l2_cache();
	crc        = crc32((unsigned char *)SPIFLASH_BASE, SPI_FLASH_BLOCK_SIZE);
	crc_test   = crc;

#ifdef SPIFLASH_DEBUG
	printf("Testing against CRC32: %08x\n\r", crc);
#endif

	/* Check if block is erased (filled with 0xFF) */
	if(crc == CRC32_ERASED_FLASH) {
		printf("First SPI Flash block erased, unable to perform freq test.\n\r");
		return -1;
	}
#if defined(SPIFLASH_PHY_MIN_DIVISOR) && SPIFLASH_PHY_MIN_DIVISOR == 1
	while((crc == crc_test) && (lowest_div-- > 1)) {
#else
	while((crc == crc_test) && ((lowest_div -= 2) >= 2)) {
#endif
		spiflash_phy_clk_divisor_write((uint32_t)lowest_div);
		invd_cpu_dcache_range((void *)SPIFLASH_BASE, SPI_FLASH_BLOCK_SIZE);
		flush_l2_cache();
		crc_test = crc32((unsigned char *)SPIFLASH_BASE, SPI_FLASH_BLOCK_SIZE);
#ifdef SPIFLASH_DEBUG
		printf("[DIV: %d] %08x\n\r", lowest_div, crc_test);
#endif
	}
#if defined(SPIFLASH_PHY_MIN_DIVISOR) && SPIFLASH_PHY_MIN_DIVISOR == 1
	lowest_div++;
#else
	lowest_div += 2;
#endif
#endif
	printf("SPI Flash clk configured to %d MHz (div: %d)\n", CONFIG_CLOCK_FREQUENCY/(lowest_div*1000000), lowest_div);

	spiflash_phy_clk_divisor_write(lowest_div);
#ifdef CSR_SPIFLASH_MMAP_CLK_DIVISOR_ADDR
	spiflash_mmap_clk_divisor_write(lowest_div);
#endif

#else

	printf("SPI Flash clk configured to %d MHz\n", (int)(SPIFLASH_PHY_FREQUENCY/1000000));

#endif

	return 0;
}

void spiflash_dummy_bits_setup(unsigned int dummy_bits)
{
#ifdef CSR_SPIFLASH_MMAP_DUMMY_BITS_ADDR
	spiflash_mmap_dummy_bits_write((uint32_t)dummy_bits);
#ifdef SPIFLASH_DEBUG
	printf("Dummy bits set to: %" PRIx32 "\n\r", spiflash_mmap_dummy_bits_read());
#endif
#else
	(void)dummy_bits;
#endif
}

#ifdef CSR_SPIFLASH_MASTER_CS_ADDR

static void spiflash_len_mask_width_write(uint32_t len, uint32_t width, uint32_t mask)
{
	uint32_t tmp = len & ((1 <<  CSR_SPIFLASH_MASTER_PHYCONFIG_LEN_SIZE) - 1);
	uint32_t word = tmp << CSR_SPIFLASH_MASTER_PHYCONFIG_LEN_OFFSET;
	tmp = width & ((1 << CSR_SPIFLASH_MASTER_PHYCONFIG_WIDTH_SIZE) - 1);
	word |= tmp << CSR_SPIFLASH_MASTER_PHYCONFIG_WIDTH_OFFSET;
	tmp = mask & ((1 <<  CSR_SPIFLASH_MASTER_PHYCONFIG_MASK_SIZE) - 1);
	word |= tmp << CSR_SPIFLASH_MASTER_PHYCONFIG_MASK_OFFSET;
	spiflash_master_phyconfig_write(word);
}

static bool spiflash_tx_ready(void)
{
	return (spiflash_master_status_read() >> CSR_SPIFLASH_MASTER_STATUS_TX_READY_OFFSET) & 1;
}

static bool spiflash_rx_ready(void)
{
	return (spiflash_master_status_read() >> CSR_SPIFLASH_MASTER_STATUS_RX_READY_OFFSET) & 1;
}

static void spiflash_master_write(uint32_t val, size_t len, size_t width, uint32_t mask)
{
	/* Be sure to empty RX queue before doing Xfer. */
	while (spiflash_rx_ready())
		spiflash_master_rxtx_read();

	/* Configure Master */
	spiflash_len_mask_width_write(8*len, width, mask);

	/* Set CS. */
	spiflash_master_cs_write(1);

	/* Do Xfer. */
	spiflash_master_rxtx_write(val);
	while (!spiflash_rx_ready());

	/* Clear RX queue. */
	spiflash_master_rxtx_read();

	/* Clear CS. */
	spiflash_master_cs_write(0);
}

static volatile uint8_t w_buf[SPI_FLASH_BLOCK_SIZE + 4];
static volatile uint8_t r_buf[SPI_FLASH_BLOCK_SIZE + 4];

static uint32_t transfer_byte(uint8_t b)
{
	/* wait for tx ready */
	while (!spiflash_tx_ready());

	spiflash_master_rxtx_write((uint32_t)b);

	/* wait for rx ready */
	while (!spiflash_rx_ready());

	return spiflash_master_rxtx_read();
}

static void transfer_cmd(volatile uint8_t *bs, volatile uint8_t *resp, int len)
{
	spiflash_len_mask_width_write(8, 1, 1);
	spiflash_master_cs_write(1);

	for (int i=0; i < len; i++) {
		resp[i] = transfer_byte(bs[i]);
	}

	spiflash_master_cs_write(0);
}

static uint32_t spiflash_read_id_register(void)
{
	volatile uint8_t buf[4];
	w_buf[0] = 0x9F;
	w_buf[1] = 0x00;
	transfer_cmd(w_buf, buf, 4);

#ifdef SPIFLASH_DEBUG
	printf("[ID: %02x %02x %02x %02x]\n", buf[0], buf[1], buf[2], buf[3]);
#endif

	/* FIXME normally the status should be in buf[1],
	   but we have to read it a few more times to be
	   stable for unknown reasons */
	return buf[3];
}

static uint32_t spiflash_read_register(uint8_t command)
{
	volatile uint8_t buf[4];
	w_buf[0] = command;
	w_buf[1] = 0x00;
	transfer_cmd(w_buf, buf, 4);

#ifdef SPIFLASH_DEBUG
	printf("[REG %02x: %02x %02x %02x %02x]\n", command, buf[0], buf[1], buf[2], buf[3]);
#endif

	/* FIXME normally the status should be in buf[1],
	   but we have to read it a few more times to be
	   stable for unknown reasons */
	return buf[3];
}

static uint32_t spiflash_read_status_register(void)
{
	return spiflash_read_register(0x05);
}

static void spiflash_write_enable(void)
{
	uint8_t buf[1];
	w_buf[0] = 0x06;
	transfer_cmd(w_buf, buf, 1);
}

#ifdef SPIFLASH_MODULE_QUAD_CAPABLE
#define SPIFLASH_READY_TIMEOUT 1000
#define SPIFLASH_SR1_QE_BIT6   0x40
#define SPIFLASH_SR1_WRITABLE  0xfc

static bool spiflash_wait_until_ready(void)
{
	for (unsigned int timeout = 0; timeout < SPIFLASH_READY_TIMEOUT; timeout++) {
		if ((spiflash_read_status_register() & 1) == 0)
			return true;
#ifdef SPIFLASH_DEBUG
		printf(".");
#endif
		cdelay(CONFIG_CLOCK_FREQUENCY/1000);
	}

	return (spiflash_read_status_register() & 1) == 0;
}

static bool spiflash_enable_quad_mode(void)
{
#if defined(SPIFLASH_MODULE_QUAD_ENABLE_WRSR_SR1_BIT6)
	uint32_t sr = spiflash_read_status_register();

	if (sr == 0xff) {
		printf("Unable to read SPI Flash status register.\n");
		return false;
	}

	if (sr & SPIFLASH_SR1_QE_BIT6)
		return true;

	spiflash_write_enable();
	/* Preserve writable SR1 bits while excluding the WIP/WEL status bits. */
	spiflash_master_write((0x01 << 8) | ((sr | SPIFLASH_SR1_QE_BIT6) & SPIFLASH_SR1_WRITABLE), 2, 1, 0x1);
#elif defined(SPIFLASH_MODULE_QUAD_ENABLE_WRR_CR1_BIT1)
	uint32_t sr = spiflash_read_status_register();
	uint32_t cr = spiflash_read_register(0x35);

	if ((sr == 0xff) || (cr == 0xff)) {
		printf("Unable to read SPI Flash status/configuration registers.\n");
		return false;
	}

	spiflash_write_enable();
	spiflash_master_write((0x01 << 16) | ((sr & 0x9c) << 8) | ((cr | 0x02) & 0xff), 3, 1, 0x1);
#else
	spiflash_master_write(0x00000006, 1, 1, 0x1);
	spiflash_master_write(0x00014307, 3, 1, 0x1);
#endif

	if (!spiflash_wait_until_ready()) {
		printf("SPI Flash quad enable timeout.\n");
		return false;
	}

#if defined(SPIFLASH_MODULE_QUAD_ENABLE_WRSR_SR1_BIT6)
	sr = spiflash_read_status_register();
	if ((sr == 0xff) || ((sr & SPIFLASH_SR1_QE_BIT6) == 0)) {
		printf("SPI Flash quad enable failed.\n");
		return false;
	}
#elif defined(SPIFLASH_MODULE_QUAD_ENABLE_WRR_CR1_BIT1)
	if ((spiflash_read_register(0x35) & 0x02) == 0) {
		printf("SPI Flash quad enable failed.\n");
		return false;
	}
#endif

	return true;
}
#endif

static void page_program(uint32_t addr, uint8_t *data, int len)
{
	w_buf[0] = 0x02;
	w_buf[1] = addr>>16;
	w_buf[2] = addr>>8;
	w_buf[3] = addr>>0;
	memcpy((void *)w_buf+4, (void *)data, len);
	transfer_cmd(w_buf, r_buf, len+4);
}

static void spiflash_erase_command(uint32_t addr, uint8_t opcode, uint8_t addr_bits)
{
	uint8_t addr_bytes = addr_bits/8;

	w_buf[0] = opcode;
	for (uint8_t i = 0; i < addr_bytes; i++)
		w_buf[1+i] = addr >> (8*(addr_bytes - i - 1));
	transfer_cmd(w_buf, r_buf, 1 + addr_bytes);
}

/* Compatibility with LiteSPI module definitions predating erase geometry. */
#ifndef SPIFLASH_MODULE_ERASE_OPCODE
#define SPIFLASH_MODULE_ERASE_OPCODE    0xd8
#define SPIFLASH_MODULE_ERASE_SIZE      (64*1024)
#define SPIFLASH_MODULE_ERASE_ADDR_BITS 24
#endif

#define min(x, y) (((x) < (y)) ? (x) : (y))

void spiflash_erase_range(uint32_t addr, uint32_t len)
{
	uint32_t erase_addr;
	uint32_t last_addr;

	if (len == 0)
		return;
	if (addr > UINT32_MAX - (len - 1)) {
		printf("Error: SPI Flash erase range wraps the address space.\n");
		return;
	}

	erase_addr = addr - (addr % SPIFLASH_MODULE_ERASE_SIZE);
	last_addr  = addr + len - 1;
	last_addr -= last_addr % SPIFLASH_MODULE_ERASE_SIZE;

	for (;;) {
		printf("Erase SPI Flash @0x%08lx", erase_addr);
		spiflash_write_enable();
		spiflash_erase_command(
			erase_addr,
			SPIFLASH_MODULE_ERASE_OPCODE,
			SPIFLASH_MODULE_ERASE_ADDR_BITS);

		while (spiflash_read_status_register() & 1) {
			printf(".");
			cdelay(CONFIG_CLOCK_FREQUENCY/25);
		}
		printf("\n");

#ifdef SPIFLASH_BASE
		invd_cpu_dcache_range(
			(void *)SPIFLASH_BASE + erase_addr,
			SPIFLASH_MODULE_ERASE_SIZE);

		/* check if region was really erased */
		for (uint32_t j = 0; j < SPIFLASH_MODULE_ERASE_SIZE; j++) {
			uint8_t* peek = (((uint8_t*)SPIFLASH_BASE)+erase_addr+j);
			if (*peek != 0xff) {
				printf("Error: location 0x%08lx not erased (%0x2x)\n", erase_addr+j, *peek);
			}
		}
#endif

		if (erase_addr == last_addr)
			break;
		erase_addr += SPIFLASH_MODULE_ERASE_SIZE;
	}
}

void spiflash_erase_4k_sector(uint32_t addr)
{
	spiflash_write_enable();
	spiflash_erase_command(addr, 0x20, 24);
	while (spiflash_read_status_register() & 1);
}

/* Returns the number of bytes written and verified, or -1 when the readback
   verification failed (e.g. region not erased beforehand). */
int spiflash_write_stream(uint32_t addr, uint8_t *stream, uint32_t len)
{
	int res = 0;
	uint32_t errors = 0;
	uint32_t w_len = min(len, SPI_FLASH_BLOCK_SIZE);
	uint32_t offset = 0;

#ifdef SPIFLASH_DEBUG
	printf("Write SPI Flash @0x%08lx", ((uint32_t)addr));
#endif

	while(w_len) {
		spiflash_write_enable();
		page_program(addr+offset, stream+offset, w_len);

		while(spiflash_read_status_register() & 1) {
#ifdef SPIFLASH_DEBUG
			printf(".");
#endif
		}

#ifdef SPIFLASH_BASE
		invd_cpu_dcache_range((void *)SPIFLASH_BASE + addr + offset, w_len);

		for (uint32_t j = 0; j < w_len; j++) {
			uint8_t* peek = (((uint8_t*)SPIFLASH_BASE)+addr+offset+j);
			if (*peek != stream[offset+j]) {
				printf("Error: verify failed at 0x%08lx (0x%02x should be 0x%02x)\n", (uint32_t)peek, *peek, stream[offset+j]);
				errors++;
			}
		}
#endif

		offset += w_len;
		w_len = min(len-offset, SPI_FLASH_BLOCK_SIZE);
		res = offset;
	}
#ifdef SPIFLASH_DEBUG
  printf("\n");
#endif
	if (errors)
		return -1;
	return res;
}

#endif

void spiflash_memspeed(void) {
#ifdef SPIFLASH_BASE
	/* Test Sequential Read accesses */
	memspeed((unsigned int *) SPIFLASH_BASE, 4096, 1, 0);

	/* Test Random Read accesses */
	memspeed((unsigned int *) SPIFLASH_BASE, 4096, 1, 1);
#endif
}

void spiflash_init(void)
{
#ifdef SPIFLASH_BASE
	printf("\nInitializing %s SPI Flash @0x%08lx...\n", SPIFLASH_MODULE_NAME, SPIFLASH_BASE);
#else
	printf("\nInitializing %s SPI Flash...\n", SPIFLASH_MODULE_NAME);
#endif

#ifdef SPIFLASH_MODULE_DUMMY_BITS
	spiflash_dummy_bits_setup(SPIFLASH_MODULE_DUMMY_BITS);
#endif

#ifdef CSR_SPIFLASH_MASTER_CS_ADDR

	spiflash_read_id_register();

	/* Quad / QPI Configuration. */
#ifdef SPIFLASH_MODULE_QUAD_CAPABLE
	printf("Enabling Quad mode...\n");
	if (!spiflash_enable_quad_mode())
		return;

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
