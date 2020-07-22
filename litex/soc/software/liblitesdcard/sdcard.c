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

static void busy_wait_us(unsigned int us)
{
    timer0_en_write(0);
    timer0_reload_write(0);
    timer0_load_write(CONFIG_CLOCK_FREQUENCY/1000000*us);
    timer0_en_write(1);
    timer0_update_value_write(1);
    while(timer0_value_read()) timer0_update_value_write(1);
}

int sdcard_wait_cmd_done(void) {
	unsigned int cmdevt;
	while (1) {
		cmdevt = sdcore_cmd_event_read();
		busy_wait_us(1);
#ifdef SDCARD_DEBUG
		printf("cmdevt: %08x\n", cmdevt);
#endif
		if (cmdevt & 0x1) {
			if (cmdevt & 0x4) {
#ifdef SDCARD_DEBUG
				printf("cmdevt: SD_TIMEOUT\n");
#endif
				return SD_TIMEOUT;
			}
			else if (cmdevt & 0x8) {
#ifdef SDCARD_DEBUG
				printf("cmdevt: SD_CRCERROR\n");
#endif
				return SD_CRCERROR;
			}
			return SD_OK;
		}
	}
}

int sdcard_wait_data_done(void) {
	unsigned int dataevt;
	while (1) {
		dataevt = sdcore_data_event_read();
		busy_wait_us(1);
#ifdef SDCARD_DEBUG
		printf("dataevt: %08x\n", dataevt);
#endif
		if (dataevt & 0x1) {
			if (dataevt & 0x4)
				return SD_TIMEOUT;
			else if (dataevt & 0x8)
				return SD_CRCERROR;
			return SD_OK;
		}
	}
}

int sdcard_wait_response(void) {
#ifdef SDCARD_DEBUG
	int i;
#endif
	int status;

	status = sdcard_wait_cmd_done();

	csr_rd_buf_uint32(CSR_SDCORE_CMD_RESPONSE_ADDR, sdcard_response, SD_CMD_RESPONSE_SIZE/4);

#ifdef SDCARD_DEBUG
	for(i = 0; i < SD_CMD_RESPONSE_SIZE/4; i++) {
		printf("%08x ", sdcard_response[i]);
	}
	printf("\n");
#endif

	return status;
}

/*-----------------------------------------------------------------------*/
/* SDCard clocker functions                                              */
/*-----------------------------------------------------------------------*/

static uint32_t log2(uint32_t x)
{
  uint32_t r = 0 ;
  while(x >>= 1) r++;
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

int sdcard_go_idle(void) {
#ifdef SDCARD_DEBUG
	printf("CMD0: GO_IDLE\n");
#endif
	sdcore_cmd_argument_write(0x00000000);
	sdcore_cmd_command_write((0 << 8) | SDCARD_CTRL_RESPONSE_NONE);
	sdcore_cmd_send_write(1);
	return sdcard_wait_response();
}

int sdcard_send_ext_csd(void) {
	unsigned int arg;
	arg = 0x000001aa;
#ifdef SDCARD_DEBUG
	printf("CMD8: SEND_EXT_CSD, arg: 0x%08x\n", arg);
#endif
	sdcore_cmd_argument_write(arg);
	sdcore_cmd_command_write((8 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_cmd_send_write(1);
	return sdcard_wait_response();
}

int sdcard_app_cmd(int rca) {
#ifdef SDCARD_DEBUG
	printf("CMD55: APP_CMD\n");
#endif
	sdcore_cmd_argument_write(rca << 16);
	sdcore_cmd_command_write((55 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_cmd_send_write(1);
	return sdcard_wait_response();
}

int sdcard_app_send_op_cond(int hcs) {
	unsigned int arg;
	arg = 0x10ff8000;
	if (hcs)
		arg |= 0x60000000;
#ifdef SDCARD_DEBUG
	printf("ACMD41: APP_SEND_OP_COND, arg: %08x\n", arg);
#endif
	sdcore_cmd_argument_write(arg);
	sdcore_cmd_command_write((41 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_cmd_send_write(1);
	return sdcard_wait_response();
}

int sdcard_all_send_cid(void) {
#ifdef SDCARD_DEBUG
	printf("CMD2: ALL_SEND_CID\n");
#endif
	sdcore_cmd_argument_write(0x00000000);
	sdcore_cmd_command_write((2 << 8) | SDCARD_CTRL_RESPONSE_LONG);
	sdcore_cmd_send_write(1);
	return sdcard_wait_response();
}

int sdcard_set_relative_address(void) {
#ifdef SDCARD_DEBUG
	printf("CMD3: SET_RELATIVE_ADDRESS\n");
#endif
	sdcore_cmd_argument_write(0x00000000);
	sdcore_cmd_command_write((3 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_cmd_send_write(1);
	return sdcard_wait_response();
}

int sdcard_send_cid(unsigned int rca) {
#ifdef SDCARD_DEBUG
	printf("CMD10: SEND_CID\n");
#endif
	sdcore_cmd_argument_write(rca << 16);
	sdcore_cmd_command_write((10 << 8) | SDCARD_CTRL_RESPONSE_LONG);
	sdcore_cmd_send_write(1);
	return sdcard_wait_response();
}

int sdcard_send_csd(unsigned int rca) {
#ifdef SDCARD_DEBUG
	printf("CMD9: SEND_CSD\n");
#endif
	sdcore_cmd_argument_write(rca << 16);
	sdcore_cmd_command_write((9 << 8) | SDCARD_CTRL_RESPONSE_LONG);
	sdcore_cmd_send_write(1);
	return sdcard_wait_response();
}

int sdcard_select_card(unsigned int rca) {
#ifdef SDCARD_DEBUG
	printf("CMD7: SELECT_CARD\n");
#endif
	sdcore_cmd_argument_write(rca << 16);
	sdcore_cmd_command_write((7 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_cmd_send_write(1);
	return sdcard_wait_response();
}

int sdcard_app_set_bus_width(void) {
#ifdef SDCARD_DEBUG
	printf("ACMD6: SET_BUS_WIDTH\n");
#endif
	sdcore_cmd_argument_write(0x00000002);
	sdcore_cmd_command_write((6 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_cmd_send_write(1);
	return sdcard_wait_response();
}

int sdcard_switch(unsigned int mode, unsigned int group, unsigned int value) {
	unsigned int arg;

#ifdef SDCARD_DEBUG
	printf("CMD6: SWITCH_FUNC\n");
#endif
	arg = (mode << 31) | 0xffffff;
	arg &= ~(0xf << (group * 4));
	arg |= value << (group * 4);

	sdcore_cmd_argument_write(arg);
	sdcore_block_length_write(64);
	sdcore_block_count_write(1);
	sdcore_cmd_command_write((6 << 8) |
				 SDCARD_CTRL_RESPONSE_SHORT |
				 (SDCARD_CTRL_DATA_TRANSFER_READ << 5));
	sdcore_cmd_send_write(1);
	sdcard_wait_response();
	return sdcard_wait_data_done();
}

int sdcard_app_send_scr(void) {
#ifdef SDCARD_DEBUG
	printf("CMD51: APP_SEND_SCR\n");
#endif
	sdcore_cmd_argument_write(0x00000000);
	sdcore_block_length_write(8);
	sdcore_block_count_write(1);
	sdcore_cmd_command_write((51 << 8) |
				 SDCARD_CTRL_RESPONSE_SHORT |
				 (SDCARD_CTRL_DATA_TRANSFER_READ << 5));
	sdcore_cmd_send_write(1);
	sdcard_wait_response();
	return sdcard_wait_data_done();
}


int sdcard_app_set_blocklen(unsigned int blocklen) {
#ifdef SDCARD_DEBUG
	printf("CMD16: SET_BLOCKLEN\n");
#endif
	sdcore_cmd_argument_write(blocklen);
	sdcore_cmd_command_write((16 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_cmd_send_write(1);
	return sdcard_wait_response();
}

int sdcard_write_single_block(unsigned int blockaddr) {
#ifdef SDCARD_DEBUG
	printf("CMD24: WRITE_SINGLE_BLOCK\n");
#endif
	int cmd_response = -1;
	while (cmd_response != SD_OK) {
		sdcore_cmd_argument_write(blockaddr);
		sdcore_block_length_write(512);
		sdcore_block_count_write(1);
		sdcore_cmd_command_write((24 << 8) |
					 SDCARD_CTRL_RESPONSE_SHORT |
					 (SDCARD_CTRL_DATA_TRANSFER_WRITE << 5));
		sdcore_cmd_send_write(1);
		cmd_response = sdcard_wait_response();
	}
	return cmd_response;
}

int sdcard_write_multiple_block(unsigned int blockaddr, unsigned int blockcnt) {
#ifdef SDCARD_DEBUG
	printf("CMD25: WRITE_MULTIPLE_BLOCK\n");
#endif
	int cmd_response = -1;
	while (cmd_response != SD_OK) {
		sdcore_cmd_argument_write(blockaddr);
		sdcore_block_length_write(512);
		sdcore_block_count_write(blockcnt);
		sdcore_cmd_command_write((25 << 8) |
					 SDCARD_CTRL_RESPONSE_SHORT |
					 (SDCARD_CTRL_DATA_TRANSFER_WRITE << 5));
		sdcore_cmd_send_write(1);
		cmd_response = sdcard_wait_response();
	}
	return cmd_response;
}

int sdcard_read_single_block(unsigned int blockaddr) {
#ifdef SDCARD_DEBUG
	printf("CMD17: READ_SINGLE_BLOCK\n");
#endif
	int cmd_response = -1;
	while (cmd_response != SD_OK) {
		sdcore_cmd_argument_write(blockaddr);
		sdcore_block_length_write(512);
		sdcore_block_count_write(1);
		sdcore_cmd_command_write((17 << 8) |
					 SDCARD_CTRL_RESPONSE_SHORT |
					 (SDCARD_CTRL_DATA_TRANSFER_READ << 5));
		sdcore_cmd_send_write(1);
		cmd_response = sdcard_wait_response();
	}
	return sdcard_wait_data_done();
}

int sdcard_read_multiple_block(unsigned int blockaddr, unsigned int blockcnt) {
#ifdef SDCARD_DEBUG
	printf("CMD18: READ_MULTIPLE_BLOCK\n");
#endif
	int cmd_response = -1;
	while (cmd_response != SD_OK) {
		sdcore_cmd_argument_write(blockaddr);
		sdcore_block_length_write(512);
		sdcore_block_count_write(blockcnt);
		sdcore_cmd_command_write((18 << 8) |
					 SDCARD_CTRL_RESPONSE_SHORT |
					 (SDCARD_CTRL_DATA_TRANSFER_READ << 5));
		sdcore_cmd_send_write(1);
		cmd_response = sdcard_wait_response();
	}
	return cmd_response;
}

int sdcard_stop_transmission(void) {
#ifdef SDCARD_DEBUG
	printf("CMD12: STOP_TRANSMISSION\n");
#endif
	sdcore_cmd_argument_write(0x0000000);
	sdcore_cmd_command_write((12 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_cmd_send_write(1);
	return sdcard_wait_response();
}

int sdcard_send_status(unsigned int rca) {
#ifdef SDCARD_DEBUG
	printf("CMD13: SEND_STATUS\n");
#endif
	sdcore_cmd_argument_write(rca << 16);
	sdcore_cmd_command_write((13 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_cmd_send_write(1);
	return sdcard_wait_response();
}

int sdcard_set_block_count(unsigned int blockcnt) {
#ifdef SDCARD_DEBUG
	printf("CMD23: SET_BLOCK_COUNT\n");
#endif
	sdcore_cmd_argument_write(blockcnt);
	sdcore_cmd_command_write((23 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_cmd_send_write(1);
	return sdcard_wait_response();
}

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

/*-----------------------------------------------------------------------*/
/* SDCard user functions                                                 */
/*-----------------------------------------------------------------------*/

int sdcard_init(void) {
	unsigned short rca;
	uint16_t timeout;

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
	sdblock2mem_dma_base_write((uint32_t) buf);
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
		sdmem2block_dma_base_write((uint32_t) buf);
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
