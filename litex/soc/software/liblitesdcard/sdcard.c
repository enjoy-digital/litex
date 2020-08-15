// This file is Copyright (c) 2017-2020 Florent Kermarrec <florent@enjoy-digital.fr>
// This file is Copyright (c) 2019 Kees Jongenburger <kees.jongenburger@gmail.com>
// This file is Copyright (c) 2018 bunnie <bunnie@kosagi.com>
// This file is Copyright (c) 2020 Antmicro <www.antmicro.com>
// License: BSD

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <generated/csr.h>
#include <generated/mem.h>
#include <system.h>

#include "fat/ff.h"
#include "fat/diskio.h"
#include "sdcard.h"

#ifdef CSR_SDCORE_BASE

//#define SDCARD_DEBUG
//#define SDCARD_CMD23_SUPPORT

#ifndef SDCARD_CLK_FREQ_INIT
#define SDCARD_CLK_FREQ_INIT 400000
#endif

#ifndef SDCARD_CLK_FREQ
#define SDCARD_CLK_FREQ 25000000
#endif

unsigned int sdcard_response[SD_CMD_RESPONSE_SIZE/4];

/*-----------------------------------------------------------------------*/
/* Helpers                                                               */
/*-----------------------------------------------------------------------*/

#define max(x, y) (((x) > (y)) ? (x) : (y))
#define min(x, y) (((x) < (y)) ? (x) : (y))

/*-----------------------------------------------------------------------*/
/* SDCard command helpers                                                */
/*-----------------------------------------------------------------------*/

int sdcard_wait_cmd_done(void) {
	unsigned int event;
	for (;;) {
		event = sdcore_cmd_event_read();
#ifdef SDCARD_DEBUG
		printf("cmdevt: %08x\n", event);
#endif
		if (event & 0x1)
			break;
		busy_wait_us(1);
	}
	if (event & 0x4)
		return SD_TIMEOUT;
	if (event & 0x8)
		return SD_CRCERROR;
	return SD_OK;
}

int sdcard_wait_data_done(void) {
	unsigned int event;
	for (;;) {
		event = sdcore_data_event_read();
#ifdef SDCARD_DEBUG
		printf("dataevt: %08x\n", event);
#endif
		if (event & 0x1)
			break;
		busy_wait_us(1);
	}
	if (event & 0x4)
		return SD_TIMEOUT;
	else if (event & 0x8)
		return SD_CRCERROR;
	return SD_OK;
}

int sdcard_wait_response(void) {
	int status = sdcard_wait_cmd_done();

	csr_rd_buf_uint32(CSR_SDCORE_CMD_RESPONSE_ADDR,
			  sdcard_response, SD_CMD_RESPONSE_SIZE/4);
#ifdef SDCARD_DEBUG
	printf("%08x %08x %08x %08x\n",
		sdcard_response[0], sdcard_response[1],
		sdcard_response[2], sdcard_response[3]);
#endif
	return status;
}

/*-----------------------------------------------------------------------*/
/* SDCard clocker functions                                              */
/*-----------------------------------------------------------------------*/

static uint32_t log2(uint32_t x)
{
	uint32_t r = 0;
	while(x >>= 1)
		r++;
	return r;
}

static void sdcard_set_clk_freq(uint32_t clk_freq) {
	uint32_t divider;
	divider = CONFIG_CLOCK_FREQUENCY/clk_freq + 1;
	divider = (1 << log2(divider));
	divider = max(divider,   2);
	divider = min(divider, 256);
#ifdef SDCARD_DEBUG
	printf("Setting SDCard clk freq to ");
	if (clk_freq > 1000000)
		printf("%d MHz\n", (CONFIG_CLOCK_FREQUENCY/divider)/1000000);
	else
		printf("%d KHz\n", (CONFIG_CLOCK_FREQUENCY/divider)/1000);
#endif
	sdphy_clocker_divider_write(divider);
}

/*-----------------------------------------------------------------------*/
/* SDCard commands functions                                             */
/*-----------------------------------------------------------------------*/

static inline int sdcard_send_command(uint32_t arg, uint8_t cmd, uint8_t rsp) {
	sdcore_cmd_argument_write(arg);
	sdcore_cmd_command_write((cmd << 8) | rsp);
	sdcore_cmd_send_write(1);
	return sdcard_wait_response();
}

int sdcard_go_idle(void) {
#ifdef SDCARD_DEBUG
	printf("CMD0: GO_IDLE\n");
#endif
	return sdcard_send_command(0, 0, SDCARD_CTRL_RESPONSE_NONE);
}

int sdcard_send_ext_csd(void) {
	uint32_t arg = 0x000001aa;
#ifdef SDCARD_DEBUG
	printf("CMD8: SEND_EXT_CSD, arg: 0x%08x\n", arg);
#endif
	return sdcard_send_command(arg, 8, SDCARD_CTRL_RESPONSE_SHORT);
}

int sdcard_app_cmd(uint16_t rca) {
#ifdef SDCARD_DEBUG
	printf("CMD55: APP_CMD\n");
#endif
	return sdcard_send_command(rca << 16, 55, SDCARD_CTRL_RESPONSE_SHORT);
}

int sdcard_app_send_op_cond(int hcs) {
	uint32_t arg = 0x10ff8000;
	if (hcs)
		arg |= 0x60000000;
#ifdef SDCARD_DEBUG
	printf("ACMD41: APP_SEND_OP_COND, arg: %08x\n", arg);
#endif
	return sdcard_send_command(arg, 41, SDCARD_CTRL_RESPONSE_SHORT);
}

int sdcard_all_send_cid(void) {
#ifdef SDCARD_DEBUG
	printf("CMD2: ALL_SEND_CID\n");
#endif
	return sdcard_send_command(0, 2, SDCARD_CTRL_RESPONSE_LONG);
}

int sdcard_set_relative_address(void) {
#ifdef SDCARD_DEBUG
	printf("CMD3: SET_RELATIVE_ADDRESS\n");
#endif
	return sdcard_send_command(0, 3, SDCARD_CTRL_RESPONSE_SHORT);
}

int sdcard_send_cid(uint16_t rca) {
#ifdef SDCARD_DEBUG
	printf("CMD10: SEND_CID\n");
#endif
	return sdcard_send_command(rca << 16, 10, SDCARD_CTRL_RESPONSE_LONG);
}

int sdcard_send_csd(uint16_t rca) {
#ifdef SDCARD_DEBUG
	printf("CMD9: SEND_CSD\n");
#endif
	return sdcard_send_command(rca << 16, 9, SDCARD_CTRL_RESPONSE_LONG);
}

int sdcard_select_card(uint16_t rca) {
#ifdef SDCARD_DEBUG
	printf("CMD7: SELECT_CARD\n");
#endif
	return sdcard_send_command(rca << 16, 7, SDCARD_CTRL_RESPONSE_SHORT);
}

int sdcard_app_set_bus_width(void) {
#ifdef SDCARD_DEBUG
	printf("ACMD6: SET_BUS_WIDTH\n");
#endif
	return sdcard_send_command(2, 6, SDCARD_CTRL_RESPONSE_SHORT);
}

int sdcard_switch(unsigned int mode, unsigned int group, unsigned int value) {
	unsigned int arg;
	arg = (mode << 31) | 0xffffff;
	arg &= ~(0xf << (group * 4));
	arg |= value << (group * 4);
#ifdef SDCARD_DEBUG
	printf("CMD6: SWITCH_FUNC\n");
#endif
	sdcore_block_length_write(64);
	sdcore_block_count_write(1);
	return sdcard_send_command(arg, 6,
				   (SDCARD_CTRL_DATA_TRANSFER_READ << 5) |
				   SDCARD_CTRL_RESPONSE_SHORT);
}

int sdcard_app_send_scr(void) {
#ifdef SDCARD_DEBUG
	printf("CMD51: APP_SEND_SCR\n");
#endif
	sdcore_block_length_write(8);
	sdcore_block_count_write(1);
	return sdcard_send_command(0, 51,
				   (SDCARD_CTRL_DATA_TRANSFER_READ << 5) |
				   SDCARD_CTRL_RESPONSE_SHORT);
}

int sdcard_app_set_blocklen(unsigned int blocklen) {
#ifdef SDCARD_DEBUG
	printf("CMD16: SET_BLOCKLEN\n");
#endif
	return sdcard_send_command(blocklen, 16, SDCARD_CTRL_RESPONSE_SHORT);
}

int sdcard_write_single_block(unsigned int blockaddr) {
#ifdef SDCARD_DEBUG
	printf("CMD24: WRITE_SINGLE_BLOCK\n");
#endif
	do {
		sdcore_block_length_write(512);
		sdcore_block_count_write(1);
	} while (sdcard_send_command(blockaddr, 24,
				     (SDCARD_CTRL_DATA_TRANSFER_WRITE << 5) |
				     SDCARD_CTRL_RESPONSE_SHORT) != SD_OK);
	return SD_OK;
}

int sdcard_write_multiple_block(unsigned int blockaddr, unsigned int blockcnt) {
#ifdef SDCARD_DEBUG
	printf("CMD25: WRITE_MULTIPLE_BLOCK\n");
#endif
	do {
		sdcore_block_length_write(512);
		sdcore_block_count_write(blockcnt);
	} while (sdcard_send_command(blockaddr, 25,
				     (SDCARD_CTRL_DATA_TRANSFER_WRITE << 5) |
				     SDCARD_CTRL_RESPONSE_SHORT) != SD_OK);
	return SD_OK;
}

int sdcard_read_single_block(unsigned int blockaddr) {
#ifdef SDCARD_DEBUG
	printf("CMD17: READ_SINGLE_BLOCK\n");
#endif
	do {
		sdcore_block_length_write(512);
		sdcore_block_count_write(1);
	} while (sdcard_send_command(blockaddr, 17,
				     (SDCARD_CTRL_DATA_TRANSFER_READ << 5) |
				     SDCARD_CTRL_RESPONSE_SHORT) != SD_OK);
	return sdcard_wait_data_done();
}

int sdcard_read_multiple_block(unsigned int blockaddr, unsigned int blockcnt) {
#ifdef SDCARD_DEBUG
	printf("CMD18: READ_MULTIPLE_BLOCK\n");
#endif
	do {
		sdcore_block_length_write(512);
		sdcore_block_count_write(blockcnt);
	} while (sdcard_send_command(blockaddr, 18,
				     (SDCARD_CTRL_DATA_TRANSFER_READ << 5) |
				     SDCARD_CTRL_RESPONSE_SHORT) != SD_OK);
	return SD_OK; // FIXME(gls): why not `sdcard_wait_data_done` like single
}

int sdcard_stop_transmission(void) {
#ifdef SDCARD_DEBUG
	printf("CMD12: STOP_TRANSMISSION\n");
#endif
	return sdcard_send_command(0, 12, SDCARD_CTRL_RESPONSE_SHORT);
}

int sdcard_send_status(uint16_t rca) {
#ifdef SDCARD_DEBUG
	printf("CMD13: SEND_STATUS\n");
#endif
	return sdcard_send_command(rca << 16, 13, SDCARD_CTRL_RESPONSE_SHORT);
}

int sdcard_set_block_count(unsigned int blockcnt) {
#ifdef SDCARD_DEBUG
	printf("CMD23: SET_BLOCK_COUNT\n");
#endif
	return sdcard_send_command(blockcnt, 23, SDCARD_CTRL_RESPONSE_SHORT);
}

#ifdef SDCARD_DEBUG
void sdcard_decode_cid(void) {
	printf(
		"CID Register: 0x%08x%08x%08x%08x\n"
		"Manufacturer ID: 0x%x\n"
		"Application ID 0x%x\n"
		"Product name: %c%c%c%c%c\n",
			sdcard_response[0],
			sdcard_response[1],
			sdcard_response[2],
			sdcard_response[3],

			(sdcard_response[0] >> 16) & 0xffff,

			sdcard_response[0] & 0xffff,

			(sdcard_response[1] >> 24) & 0xff,
			(sdcard_response[1] >> 16) & 0xff,
			(sdcard_response[1] >>  8) & 0xff,
			(sdcard_response[1] >>  0) & 0xff,
			(sdcard_response[2] >> 24) & 0xff
		);
	int crc = sdcard_response[3] & 0x000000FF;
	int month = (sdcard_response[3] & 0x00000F00) >> 8;
	int year = (sdcard_response[3] & 0x000FF000) >> 12;
	int psn = ((sdcard_response[3] & 0xFF000000) >> 24) | ((sdcard_response[2] & 0x00FFFFFF) << 8);
	printf( "CRC: %02x\n", crc);
	printf( "Production date(m/yy): %d/%d\n", month, year);
	printf( "PSN: %08x\n", psn);
	printf( "OID: %c%c\n", (sdcard_response[0] & 0x00FF0000) >> 16, (sdcard_response[0] & 0x0000FF00) >> 8);
}

void sdcard_decode_csd(void) {
	/* FIXME: only support CSR structure version 2.0 */

	int size = ((sdcard_response[2] & 0xFFFF0000) >> 16) + ((sdcard_response[1] & 0x000000FF) << 16) + 1;
	printf(
		"CSD Register: 0x%x%08x%08x%08x\n"
		"Max data transfer rate: %d MB/s\n"
		"Max read block length: %d bytes\n"
		"Device size: %d GB\n",
			sdcard_response[0],
			sdcard_response[1],
			sdcard_response[2],
			sdcard_response[3],

			(sdcard_response[0] >> 24) & 0xff,

			(1 << ((sdcard_response[1] >> 16) & 0xf)),

			size * 512 / (1024 * 1024)
	);
}
#endif

/*-----------------------------------------------------------------------*/
/* SDCard user functions                                                 */
/*-----------------------------------------------------------------------*/

int sdcard_init(void) {
	uint16_t rca, timeout;

	/* Set SD clk freq to Initialization frequency */
	sdcard_set_clk_freq(SDCARD_CLK_FREQ_INIT);
	busy_wait(1);

	for (timeout=1000; timeout>0; timeout--) {
		/* Set SDCard in SPI Mode (generate 80 dummy clocks) */
		sdphy_init_initialize_write(1);
		busy_wait(1);

		/* Set SDCard in Idle state */
		if (sdcard_go_idle() == SD_OK)
			break;
		busy_wait(1);
	}
	if (timeout == 0)
		return 0;

	/* Set SDCard voltages, only supported by ver2.00+ SDCards */
	if (sdcard_send_ext_csd() != SD_OK)
		return 0;

	/* Set SD clk freq to Operational frequency */
	sdcard_set_clk_freq(SDCARD_CLK_FREQ);
	busy_wait(1);

	/* Set SDCard in Operational state */
	for (timeout=1000; timeout>0; timeout--) {
		sdcard_app_cmd(0);
		if (sdcard_app_send_op_cond(1) != SD_OK)
			break;
		busy_wait(1);
	}
	if (timeout == 0)
		return 0;

	/* Send identification */
	if (sdcard_all_send_cid() != SD_OK)
		return 0;
#ifdef SDCARD_DEBUG
	sdcard_decode_cid();
#endif
	/* Set Relative Card Address (RCA) */
	if (sdcard_set_relative_address() != SD_OK)
		return 0;
	rca = (sdcard_response[3] >> 16) & 0xffff;

	/* Set CID */
	if (sdcard_send_cid(rca) != SD_OK)
		return 0;
#ifdef SDCARD_DEBUG
	/* FIXME: add cid decoding (optional) */
#endif

	/* Set CSD */
	if (sdcard_send_csd(rca) != SD_OK)
		return 0;
#ifdef SDCARD_DEBUG
	sdcard_decode_csd();
#endif

	/* Select card */
	if (sdcard_select_card(rca) != SD_OK)
		return 0;

	/* Set bus width */
	if (sdcard_app_cmd(rca) != SD_OK)
		return 0;
	if(sdcard_app_set_bus_width() != SD_OK)
		return 0;

	/* Switch speed */
	if (sdcard_switch(SD_SWITCH_SWITCH, SD_GROUP_ACCESSMODE, SD_SPEED_SDR50) != SD_OK)
		return 0;

	/* Switch driver strength */
	if (sdcard_switch(SD_SWITCH_SWITCH, SD_GROUP_DRIVERSTRENGTH, SD_DRIVER_STRENGTH_D) != SD_OK)
		return 0;

	/* Send SCR */
	/* FIXME: add scr decoding (optional) */
	if (sdcard_app_cmd(rca) != SD_OK)
		return 0;
	if (sdcard_app_send_scr() != SD_OK)
		return 0;

	/* Set block length */
	if (sdcard_app_set_blocklen(512) != SD_OK)
		return 0;

	return 1;
}

#ifdef CSR_SDBLOCK2MEM_BASE

void sdcard_read(uint32_t sector, uint32_t count, uint8_t* buf)
{
	/* Initialize DMA Writer */
	sdblock2mem_dma_enable_write(0);
	sdblock2mem_dma_base_write((uint64_t) buf);
	sdblock2mem_dma_length_write(512*count);
	sdblock2mem_dma_enable_write(1);

	/* Read Block(s) from SDCard */
#ifdef SDCARD_CMD23_SUPPORT
	sdcard_set_block_count(count);
#endif
	sdcard_read_multiple_block(sector, count);

	/* Wait for DMA Writer to complete */
	while ((sdblock2mem_dma_done_read() & 0x1) == 0);

	sdcard_stop_transmission();

#ifndef CONFIG_CPU_HAS_DMA_BUS
	/* Flush CPU caches */
	flush_cpu_dcache();
#ifdef CONFIG_L2_SIZE
	flush_l2_cache();
#endif
#endif
}

#endif

#ifdef CSR_SDMEM2BLOCK_BASE

void sdcard_write(uint32_t sector, uint32_t count, uint8_t* buf)
{
	while (count--) {
		/* Initialize DMA Reader */
		sdmem2block_dma_enable_write(0);
		sdmem2block_dma_base_write((uint64_t) buf);
		sdmem2block_dma_length_write(512);
		sdmem2block_dma_enable_write(1);

		/* Wait for DMA Reader to complete */
		while ((sdmem2block_dma_done_read() & 0x1) == 0);

		/* Write Single Block to SDCard */
#ifndef SDCARD_CMD23_SUPPORT
		sdcard_set_block_count(1);
#endif
		sdcard_write_single_block(sector);

		sdcard_stop_transmission();

		/* Update buf/sector */
		buf    += 512;
		sector += 1;
	}
}
#endif

/*-----------------------------------------------------------------------*/
/* SDCard FatFs disk functions                                           */
/*-----------------------------------------------------------------------*/

static DSTATUS sdcardstatus = STA_NOINIT;

DSTATUS disk_status(uint8_t drv) {
	if (drv) return STA_NOINIT;
	return sdcardstatus;
}

DSTATUS disk_initialize(uint8_t drv) {
	if (drv) return STA_NOINIT;
	if (sdcardstatus)
		sdcardstatus = sdcard_init() ? 0 : STA_NOINIT;
	return sdcardstatus;
}

DRESULT disk_read(uint8_t drv, uint8_t *buf, uint32_t sector, uint32_t count) {
	sdcard_read(sector, count, buf);
	return RES_OK;
}

#endif /* CSR_SDCORE_BASE */
