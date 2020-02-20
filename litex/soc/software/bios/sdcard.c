// This file is Copyright (c) 2017 Florent Kermarrec <florent@enjoy-digital.fr>
// This file is Copyright (c) 2019 Kees Jongenburger <kees.jongenburger@gmail.com>
// This file is Copyright (c) 2018 bunnie <bunnie@kosagi.com>
// License: BSD

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <generated/csr.h>
#include <generated/mem.h>
#include <hw/flags.h>
#include <system.h>

#include "sdcard.h"

#ifdef CSR_SDCORE_BASE

#define SDCARD_DEBUG

/* clocking */

#ifdef CSR_SDCLK_CMD_DATA_ADDR

static void sdclk_dcm_write(int cmd, int data)
{
	int word;
	word = (data << 2) | cmd;
	sdclk_cmd_data_write(word);
	sdclk_send_cmd_data_write(1);
	while(sdclk_status_read() & CLKGEN_STATUS_BUSY);
}

/* FIXME: add vco frequency check */
static void sdclk_get_config(unsigned int freq, unsigned int *best_m, unsigned int *best_d)
{
	unsigned int ideal_m, ideal_d;
	unsigned int bm, bd;
	unsigned int m, d;
	unsigned int diff_current;
	unsigned int diff_tested;

	ideal_m = freq;
	ideal_d = 5000;

	bm = 1;
	bd = 0;
	for(d=1;d<=256;d++)
		for(m=2;m<=256;m++) {
			/* common denominator is d*bd*ideal_d */
			diff_current = abs(d*ideal_d*bm - d*bd*ideal_m);
			diff_tested = abs(bd*ideal_d*m - d*bd*ideal_m);
			if(diff_tested < diff_current) {
				bm = m;
				bd = d;
			}
		}
	*best_m = bm;
	*best_d = bd;
}

void sdclk_set_clk(unsigned int freq) {
	unsigned int clk_m, clk_d;

	sdclk_get_config(100*freq, &clk_m, &clk_d);
	sdclk_dcm_write(0x1, clk_d-1);
	sdclk_dcm_write(0x3, clk_m-1);
	sdclk_send_go_write(1);
	while(!(sdclk_status_read() & CLKGEN_STATUS_PROGDONE));
	while(!(sdclk_status_read() & CLKGEN_STATUS_LOCKED));
}

#else

static void sdclk_mmcm_write(unsigned int adr, unsigned int data) {
	sdclk_mmcm_adr_write(adr);
	sdclk_mmcm_dat_w_write(data);
	sdclk_mmcm_write_write(1);
	while(!sdclk_mmcm_drdy_read());
}


static void sdclk_set_config(unsigned int m, unsigned int d) {
	/* clkfbout_mult = m */
	if(m%2)
		sdclk_mmcm_write(0x14, 0x1000 | ((m/2)<<6) | (m/2 + 1));
	else
		sdclk_mmcm_write(0x14, 0x1000 | ((m/2)<<6) | m/2);
	/* divclk_divide = d */
	if (d == 1)
		sdclk_mmcm_write(0x16, 0x1000);
	else if(d%2)
		sdclk_mmcm_write(0x16, ((d/2)<<6) | (d/2 + 1));
	else
		sdclk_mmcm_write(0x16, ((d/2)<<6) | d/2);
	/* clkout0_divide = 10 */
	sdclk_mmcm_write(0x8, 0x1000 | (5<<6) | 5);
	/* clkout1_divide = 2 */
	sdclk_mmcm_write(0xa, 0x1000 | (1<<6) | 1);
}

/* FIXME: add vco frequency check */
static void sdclk_get_config(unsigned int freq, unsigned int *best_m, unsigned int *best_d) {
	unsigned int ideal_m, ideal_d;
	unsigned int bm, bd;
	unsigned int m, d;
	unsigned int diff_current;
	unsigned int diff_tested;

	ideal_m = freq;
	ideal_d = 10000;

	bm = 1;
	bd = 0;
	for(d=1;d<=128;d++)
		for(m=2;m<=128;m++) {
			/* common denominator is d*bd*ideal_d */
			diff_current = abs(d*ideal_d*bm - d*bd*ideal_m);
			diff_tested = abs(bd*ideal_d*m - d*bd*ideal_m);
			if(diff_tested < diff_current) {
				bm = m;
				bd = d;
			}
		}
	*best_m = bm;
	*best_d = bd;
}

void sdclk_set_clk(unsigned int freq) {
	unsigned int clk_m, clk_d;

	sdclk_get_config(1000*freq, &clk_m, &clk_d);
	sdclk_set_config(clk_m, clk_d);
}

#endif

/* command utils */

static void busy_wait(unsigned int ms)
{
	timer0_en_write(0);
	timer0_reload_write(0);
	timer0_load_write(CONFIG_CLOCK_FREQUENCY/1000*ms);
	timer0_en_write(1);
	timer0_update_value_write(1);
	while(timer0_value_read()) timer0_update_value_write(1);
}

static void sdtimer_init(void)
{
	sdtimer_en_write(0);
	sdtimer_load_write(0xffffffff);
	sdtimer_reload_write(0xffffffff);
	sdtimer_en_write(1);
}

static unsigned int sdtimer_get(void)
{
	sdtimer_update_value_write(1);
	return sdtimer_value_read();
}

unsigned int sdcard_response[4];

int sdcard_wait_cmd_done(void) {
	unsigned int cmdevt;
	while (1) {
		cmdevt = sdcore_cmdevt_read();
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
				return SD_CRCERROR;
#endif
			}
			return SD_OK;
		}
	}
}

int sdcard_wait_data_done(void) {
	unsigned int dataevt;
	while (1) {
		dataevt = sdcore_dataevt_read();
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
	int status = sdcard_wait_cmd_done();

	csr_rd_buf_uint32(CSR_SDCORE_RESPONSE_ADDR, sdcard_response, 4);
#ifdef SDCARD_DEBUG
	printf("sdcard_response = [%08x, %08x, %08x, %08x];\n",
		sdcard_response[0], sdcard_response[1],
		sdcard_response[2], sdcard_response[3]);
#endif

	return status;
}

/* commands */

void sdcard_go_idle(void) {
#ifdef SDCARD_DEBUG
	printf("CMD0: GO_IDLE\n");
#endif
	sdcore_argument_write(0x00000000);
	sdcore_command_write((0 << 8) | SDCARD_CTRL_RESPONSE_NONE);
}

int sdcard_send_ext_csd(void) {
#ifdef SDCARD_DEBUG
	printf("CMD8: SEND_EXT_CSD\n");
#endif
	sdcore_argument_write(0x000001aa);
	sdcore_command_write((8 << 8) | SDCARD_CTRL_RESPONSE_NONE);
	busy_wait(1);
	return sdcard_wait_response();
}

int sdcard_app_cmd(int rca) {
#ifdef SDCARD_DEBUG
	printf("CMD55: APP_CMD\n");
#endif
	sdcore_argument_write(rca << 16);
	sdcore_command_write((55 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	busy_wait(1);
	return sdcard_wait_response();
}

int sdcard_app_send_op_cond(int hcs, int s18r) {
	unsigned int arg;
#ifdef SDCARD_DEBUG
	printf("ACMD41: APP_SEND_OP_COND\n");
#endif
	arg = 0x10ff8000;
	if (hcs)
		arg |= 0x60000000;
	if (s18r)
		arg |= 0x01000000;
	sdcore_argument_write(arg);
	sdcore_command_write((41 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	busy_wait(1);
	return sdcard_wait_response();
}

int sdcard_all_send_cid(void) {
#ifdef SDCARD_DEBUG
	printf("CMD2: ALL_SEND_CID\n");
#endif
	sdcore_argument_write(0x00000000);
	sdcore_command_write((2 << 8) | SDCARD_CTRL_RESPONSE_LONG);
	busy_wait(1);
	return sdcard_wait_response();
}

int sdcard_set_relative_address(void) {
#ifdef SDCARD_DEBUG
	printf("CMD3: SET_RELATIVE_ADDRESS\n");
#endif
	sdcore_argument_write(0x00000000);
	sdcore_command_write((3 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	busy_wait(1);
	return sdcard_wait_response();
}

int sdcard_send_cid(unsigned int rca) {
#ifdef SDCARD_DEBUG
	printf("CMD10: SEND_CID\n");
#endif
	sdcore_argument_write(rca << 16);
	sdcore_command_write((10 << 8) | SDCARD_CTRL_RESPONSE_LONG);
	busy_wait(1);
	return sdcard_wait_response();
}

int sdcard_send_csd(unsigned int rca) {
#ifdef SDCARD_DEBUG
	printf("CMD9: SEND_CSD\n");
#endif
	sdcore_argument_write(rca << 16);
	sdcore_command_write((9 << 8) | SDCARD_CTRL_RESPONSE_LONG);
	busy_wait(1);
	return sdcard_wait_response();
}

int sdcard_select_card(unsigned int rca) {
#ifdef SDCARD_DEBUG
	printf("CMD7: SELECT_CARD\n");
#endif
	sdcore_argument_write(rca << 16);
	sdcore_command_write((7 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	busy_wait(1);
	return sdcard_wait_response();
}

int sdcard_app_set_bus_width(void) {
#ifdef SDCARD_DEBUG
	printf("ACMD6: SET_BUS_WIDTH\n");
#endif
	sdcore_argument_write(0x00000002);
	sdcore_command_write((6 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	busy_wait(1);
	return sdcard_wait_response();
}

int sdcard_switch(unsigned int mode, unsigned int group, unsigned int value, unsigned int dstaddr) {
	unsigned int arg;

#ifdef SDCARD_DEBUG
	printf("CMD6: SWITCH_FUNC\n");
#endif
	arg = (mode << 31) | 0xffffff;
	arg &= ~(0xf << (group * 4));
	arg |= value << (group * 4);

	sdcore_argument_write(arg);
	sdcore_blocksize_write(64);
	sdcore_blockcount_write(1);
	sdcore_command_write((6 << 8) | SDCARD_CTRL_RESPONSE_SHORT |
						 (SDCARD_CTRL_DATA_TRANSFER_READ << 5));
	busy_wait(1);
	sdcard_wait_response();
	busy_wait(1);
	return sdcard_wait_data_done();
}

int sdcard_app_send_scr(void) {
#ifdef SDCARD_DEBUG
	printf("CMD51: APP_SEND_SCR\n");
#endif
	sdcore_argument_write(0x00000000);
	sdcore_blocksize_write(8);
	sdcore_blockcount_write(1);
	sdcore_command_write((51 << 8) | SDCARD_CTRL_RESPONSE_SHORT |
						 (SDCARD_CTRL_DATA_TRANSFER_READ << 5));
	busy_wait(1);
	sdcard_wait_response();
	busy_wait(1);
	return sdcard_wait_data_done();
}


int sdcard_app_set_blocklen(unsigned int blocklen) {
#ifdef SDCARD_DEBUG
	printf("CMD16: SET_BLOCKLEN\n");
#endif
	sdcore_argument_write(blocklen);
	sdcore_command_write((16 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	busy_wait(1);
	return sdcard_wait_response();
}

int sdcard_write_single_block(unsigned int blockaddr) {
#ifdef SDCARD_DEBUG
	printf("CMD24: WRITE_SINGLE_BLOCK\n");
#endif
	int cmd_response = -1;
	while (cmd_response != SD_OK) {
		sdcore_argument_write(blockaddr);
		sdcore_blocksize_write(512);
		sdcore_blockcount_write(1);
		sdcore_command_write((24 << 8) | SDCARD_CTRL_RESPONSE_SHORT |
							 (SDCARD_CTRL_DATA_TRANSFER_WRITE << 5));
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
		sdcore_argument_write(blockaddr);
		sdcore_blocksize_write(512);
		sdcore_blockcount_write(blockcnt);
		sdcore_command_write((25 << 8) | SDCARD_CTRL_RESPONSE_SHORT |
							 (SDCARD_CTRL_DATA_TRANSFER_WRITE << 5));
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
		sdcore_argument_write(blockaddr);
		sdcore_blocksize_write(512);
		sdcore_blockcount_write(1);
		sdcore_command_write((17 << 8) | SDCARD_CTRL_RESPONSE_SHORT |
							 (SDCARD_CTRL_DATA_TRANSFER_READ << 5));
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
		sdcore_argument_write(blockaddr);
		sdcore_blocksize_write(512);
		sdcore_blockcount_write(blockcnt);
		sdcore_command_write((18 << 8) | SDCARD_CTRL_RESPONSE_SHORT |
							 (SDCARD_CTRL_DATA_TRANSFER_READ << 5));
		cmd_response = sdcard_wait_response();
	}
	return cmd_response;
}

int sdcard_stop_transmission(void) {
#ifdef SDCARD_DEBUG
	printf("CMD12: STOP_TRANSMISSION\n");
#endif
	sdcore_argument_write(0x0000000);
	sdcore_command_write((12 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	busy_wait(1);
	return sdcard_wait_response();
}

int sdcard_send_status(unsigned int rca) {
#ifdef SDCARD_DEBUG
	printf("CMD13: SEND_STATUS\n");
#endif
	sdcore_argument_write(rca << 16);
	sdcore_command_write((13 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	busy_wait(1);
	return sdcard_wait_response();
}

int sdcard_set_block_count(unsigned int blockcnt) {
#ifdef SDCARD_DEBUG
	printf("CMD23: SET_BLOCK_COUNT\n");
#endif
	sdcore_argument_write(blockcnt);
	sdcore_command_write((23 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	busy_wait(1);
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
}

void sdcard_decode_csd(void) {
	/* FIXME: only support CSR structure version 2.0 */
	printf(
		"CSD Register: 0x%x%08x%08x%08x\n"
		"Max data transfer rate: %d MB/s\n"
		"Max read block length: %d bytes\n"
		"Device size: %d GB\n",
			sdcard_response[0],
			sdcard_response[1],
			sdcard_response[2],
			sdcard_response[3],

			(sdcard_response[1] >> 24) & 0xff,

			(1 << ((sdcard_response[1] >> 8) & 0xf)),

			((sdcard_response[2] >> 8) & 0x3fffff)*512/(1024*1024)
	);
}

/* bist */

void sdcard_bist_generator_start(unsigned int blockcnt) {
	bist_generator_reset_write(1);
	bist_generator_count_write(blockcnt);
	bist_generator_start_write(1);
}

void sdcard_bist_generator_wait(void) {
	while((bist_generator_done_read() & 0x1) == 0);
}


void sdcard_bist_checker_start(unsigned int blockcnt) {
	bist_checker_reset_write(1);
	bist_checker_count_write(blockcnt);
	bist_checker_start_write(1);
}

void sdcard_bist_checker_wait(void) {
	while((bist_checker_done_read() & 0x1) == 0);
}

/* user */

int sdcard_init(void) {
        unsigned short rca;

        /* initialize SD driver parameters */
	sdcore_cmdtimeout_write(1<<19);
	sdcore_datatimeout_write(1<<19);

	sdtimer_init();

	/* reset card */
	sdcard_go_idle();
	busy_wait(1);
	sdcard_send_ext_csd();

	/* wait for card to be ready */
	/* FIXME: 1.8v support */
	for(;;) {
		sdcard_app_cmd(0);
		sdcard_app_send_op_cond(1, 0);
		if (sdcard_response[3] & 0x80000000) {
			break;
		}
		busy_wait(1);
	}

	/* send identification */
	sdcard_all_send_cid();
#ifdef SDCARD_DEBUG
	sdcard_decode_cid();
#endif

	/* set relative card address */
	sdcard_set_relative_address();
	rca = (sdcard_response[3] >> 16) & 0xffff;

	/* set cid */
	sdcard_send_cid(rca);
#ifdef SDCARD_DEBUG
	/* FIXME: add cid decoding (optional) */
#endif

	/* set csd */
	sdcard_send_csd(rca);
#ifdef SDCARD_DEBUG
	sdcard_decode_csd();
#endif

	/* select card */
	sdcard_select_card(rca);

	/* set bus width */
	sdcard_app_cmd(rca);
	sdcard_app_set_bus_width();

	/* switch speed */
	sdcard_switch(SD_SWITCH_SWITCH, SD_GROUP_ACCESSMODE, SD_SPEED_SDR104, SRAM_BASE);

	/* switch driver strength */
	sdcard_switch(SD_SWITCH_SWITCH, SD_GROUP_DRIVERSTRENGTH, SD_DRIVER_STRENGTH_D, SRAM_BASE);

	/* send scr */
	/* FIXME: add scr decoding (optional) */
	sdcard_app_cmd(rca);
	sdcard_app_send_scr();

	/* set block length */
	sdcard_app_set_blocklen(512);

	return 0;
}

int sdcard_test(unsigned int loops) {
	unsigned int i;
	unsigned int length;
	unsigned int blocks;
	unsigned int start;
	unsigned int end;
	unsigned int errors = 0;
	unsigned long write_speed, read_speed;

	sdcore_cmdtimeout_write(1<<19);
	sdcore_datatimeout_write(1<<19);

	sdtimer_init();

	length = 4*1024*1024;
	blocks = length/512;

	for(i=0; i<loops; i++) {
		/* write */
		start = sdtimer_get();
		sdcard_set_block_count(blocks);
		sdcard_bist_generator_start(blocks);
		sdcard_write_multiple_block(i, blocks);
		sdcard_bist_generator_wait();
		sdcard_stop_transmission();
		end = sdtimer_get();
		write_speed = length*(CONFIG_CLOCK_FREQUENCY/100000)/((start - end)/100000);

		/* delay FIXME */
		busy_wait(200);

		/* read */
		start = sdtimer_get();
		sdcard_set_block_count(blocks);
		sdcard_bist_checker_start(blocks);
		sdcard_read_multiple_block(i, blocks);
		sdcard_bist_checker_wait();
		end = sdtimer_get();
		read_speed = length*(CONFIG_CLOCK_FREQUENCY/100000)/((start - end)/100000);

		/* errors */
		errors = bist_checker_errors_read();

		/* infos */
		if ((i%8) == 0)
			printf("LOOP WRITE_SPEED  READ_SPEED ERRORS\n");
		printf("%4d %6d MB/s %6d MB/s %6d\n",
			i,
			write_speed/(1024*1024),
			read_speed/(1024*1024),
			errors
		);
	}

	return errors;
}

#endif /* CSR_SDCORE_BASE */
