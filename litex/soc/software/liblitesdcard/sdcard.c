// This file is Copyright (c) 2017 Florent Kermarrec <florent@enjoy-digital.fr>
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

#include "sdcard.h"

#ifdef CSR_SDCORE_BASE

#define SDCARD_DEBUG

#define CHECK_LOOPS_PRINT_THRESHOLD 1000000

#define REPEATED_MSG(cnt, thr, fmt, ...) do { \
			const int _cnt = (cnt); \
			if((_cnt) >= (thr)) { \
				if((_cnt) > (thr)) { \
					printf("\033[1A\033[1G"); \
				} \
				printf(fmt "\033[0m\033[K\n", ## __VA_ARGS__); \
			} \
		} while(0);

#define BLOCK_SIZE 512
#define NO_RESPONSE 0xFF

#define SDCARD_RESPONSE_SIZE 5
unsigned int sdcard_response[SDCARD_RESPONSE_SIZE];

volatile char *SDREAD = (char*)(SDREAD_BASE);
volatile char *SDWRITE = (char*)(SDWRITE_BASE);

#ifdef CSR_SDCLK_CMD_DATA_ADDR

/* clocking */
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

#elif CSR_SDCLK_MMCM_DRP_WRITE_ADDR

static void sdclk_mmcm_write(unsigned int adr, unsigned int data) {
	sdclk_mmcm_drp_adr_write(adr);
	sdclk_mmcm_drp_dat_w_write(data);
	sdclk_mmcm_drp_write_write(1);
	while(!sdclk_mmcm_drp_drdy_read());
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

#else

void sdclk_set_clk(unsigned int freq) {
	printf("Unimplemented!\n");
}

#endif

/* command utils */

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


int sdcard_wait_cmd_done(void) {
	unsigned check_counter = 0;
	unsigned int cmdevt;
	while (1) {
		cmdevt = sdcore_cmdevt_read();
		REPEATED_MSG(++check_counter, CHECK_LOOPS_PRINT_THRESHOLD,
					 "\033[36m  cmdevt: %08x (check #%d)",
					 cmdevt, check_counter);
		if(check_counter > CHECK_LOOPS_PRINT_THRESHOLD) {
			putchar('\n');
			return NO_RESPONSE; //If we reach threshold, and cmdevt didn't return valid status, return NO_RESPONSE
		}
		if (cmdevt & 0x1) {
			if (cmdevt & 0x4)
				return SD_TIMEOUT;
			else if (cmdevt & 0x8)
				return SD_CRCERROR;
			return SD_OK;
		}
	}
}

int sdcard_wait_data_done(void) {
	unsigned check_counter = 0;
	unsigned int dataevt;
	while (1) {
		dataevt = sdcore_dataevt_read();
		REPEATED_MSG(++check_counter, CHECK_LOOPS_PRINT_THRESHOLD,
					 "\033[36m  dataevt: %08x (check #%d)",
					 dataevt, check_counter);
		if(check_counter > CHECK_LOOPS_PRINT_THRESHOLD) {
			putchar('\n');
			return NO_RESPONSE; //If we reach threshold, and cmdevt didn't return valid status, return NO_RESPONSE
		}
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
        int i, j;
	int status;

	status = sdcard_wait_cmd_done();

#if CONFIG_CSR_DATA_WIDTH == 8
	unsigned int r;

	// LSB is located at RESPONSE_ADDR + (RESPONSE_SIZE - 1) * 4
	int offset;
	for(i = 0; i < SDCARD_RESPONSE_SIZE; i++) {
	  r = 0;
	  for(j = 0; j < 4; j++) {
	    // SD card response consists of 17 bytes
	    // scattered accross 5 32-bit CSRs.
	    // In a configuration with CONFIG_CSR_DATA_WIDTH == 8
	    // this means we need to do 17 32-bit reads
	    // and group bytes as described below:
	    // sdcard_response | CSR_SDCORE_RESPONSE_ADDR
	    // offset          | offsets
	    // ------------------------------------------
	    //               0 | [           0 ]
	    //               1 | [  4  8 12 16 ]
	    //               2 | [ 20 23 28 32 ]
	    //               3 | [ 36 40 44 48 ]
	    //               4 | [ 52 56 60 64 ]
	    // ------------------------------------------
	    //                   |          ^  |
	    //                   +--- u32 --|--+
	    //                              LS byte
	    offset = 4 * ((CSR_SDCORE_RESPONSE_SIZE - 1) - j - i * 4);
	    if(offset >= 0) {
              // Read response and move it by 'j' bytes
	      r |= ((csr_read_simple(CSR_SDCORE_RESPONSE_ADDR + offset) & 0xFF) << (j * 8));
	    }
	  }
	  sdcard_response[(SDCARD_RESPONSE_SIZE - 1) - i] = r;  // NOTE: this is "backwards" but sticking with this because it's compatible with CSR32
	}
#else
	volatile unsigned int *buffer = (unsigned int *)CSR_SDCORE_RESPONSE_ADDR;

	for(i = 0; i < SDCARD_RESPONSE_SIZE; i++) {
		sdcard_response[i] = buffer[i];
	}
#endif

#ifdef SDCARD_DEBUG
	for(i = 0; i < SDCARD_RESPONSE_SIZE; i++) {
		printf("%08x ", sdcard_response[i]);
	}
	printf("\n");
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
	sdcore_send_write(1);
}

int sdcard_send_ext_csd(void) {
	unsigned int arg;
	arg = 0x000001aa;
#ifdef SDCARD_DEBUG
	printf("CMD8: SEND_EXT_CSD, arg: 0x%08x\n", arg);
#endif
	sdcore_argument_write(arg);
	sdcore_command_write((8 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_send_write(1);
	return sdcard_wait_response();
}

int sdcard_app_cmd(int rca) {
#ifdef SDCARD_DEBUG
	printf("CMD55: APP_CMD\n");
#endif
	sdcore_argument_write(rca << 16);
	sdcore_command_write((55 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_send_write(1);
	return sdcard_wait_response();
}

int sdcard_app_send_op_cond(int hcs, int s18r) {
	unsigned int arg;
	arg = 0x10ff8000;
	if (hcs)
		arg |= 0x60000000;
	if (s18r)
		arg |= 0x01000000;
#ifdef SDCARD_DEBUG
	printf("ACMD41: APP_SEND_OP_COND, arg: %08x\n", arg);
#endif
	sdcore_argument_write(arg);
	sdcore_command_write((41 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_send_write(1);
	return sdcard_wait_response();
}

int sdcard_all_send_cid(void) {
#ifdef SDCARD_DEBUG
	printf("CMD2: ALL_SEND_CID\n");
#endif
	sdcore_argument_write(0x00000000);
	sdcore_command_write((2 << 8) | SDCARD_CTRL_RESPONSE_LONG);
	sdcore_send_write(1);
	return sdcard_wait_response();
}

int sdcard_set_relative_address(void) {
#ifdef SDCARD_DEBUG
	printf("CMD3: SET_RELATIVE_ADDRESS\n");
#endif
	sdcore_argument_write(0x00000000);
	sdcore_command_write((3 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_send_write(1);
	return sdcard_wait_response();
}

int sdcard_send_cid(unsigned int rca) {
#ifdef SDCARD_DEBUG
	printf("CMD10: SEND_CID\n");
#endif
	sdcore_argument_write(rca << 16);
	sdcore_command_write((10 << 8) | SDCARD_CTRL_RESPONSE_LONG);
	sdcore_send_write(1);
	return sdcard_wait_response();
}

int sdcard_send_csd(unsigned int rca) {
#ifdef SDCARD_DEBUG
	printf("CMD9: SEND_CSD\n");
#endif
	sdcore_argument_write(rca << 16);
	sdcore_command_write((9 << 8) | SDCARD_CTRL_RESPONSE_LONG);
	sdcore_send_write(1);
	return sdcard_wait_response();
}

int sdcard_select_card(unsigned int rca) {
#ifdef SDCARD_DEBUG
	printf("CMD7: SELECT_CARD\n");
#endif
	sdcore_argument_write(rca << 16);
	sdcore_command_write((7 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_send_write(1);
	return sdcard_wait_response();
}

int sdcard_app_set_bus_width(void) {
#ifdef SDCARD_DEBUG
	printf("ACMD6: SET_BUS_WIDTH\n");
#endif
	sdcore_argument_write(0x00000002);
	sdcore_command_write((6 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_send_write(1);
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
	sdcore_send_write(1);
	sdcard_wait_response();
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
	sdcore_send_write(1);
	sdcard_wait_response();
	return sdcard_wait_data_done();
}


int sdcard_app_set_blocklen(unsigned int blocklen) {
#ifdef SDCARD_DEBUG
	printf("CMD16: SET_BLOCKLEN\n");
#endif
	sdcore_argument_write(blocklen);
	sdcore_command_write((16 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_send_write(1);
	return sdcard_wait_response();
}

int sdcard_write_single_block(unsigned int blockaddr) {
#ifdef SDCARD_DEBUG
	printf("CMD24: WRITE_SINGLE_BLOCK\n");
#endif
	int cmd_response = -1;
	while (cmd_response != SD_OK) {
		sdcore_argument_write(blockaddr);
		sdcore_blocksize_write(BLOCK_SIZE);
		sdcore_blockcount_write(1);
		sdcore_command_write((24 << 8) | SDCARD_CTRL_RESPONSE_SHORT |
							 (SDCARD_CTRL_DATA_TRANSFER_WRITE << 5));
		sdcore_send_write(1);
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
		sdcore_blocksize_write(BLOCK_SIZE);
		sdcore_blockcount_write(blockcnt);
		sdcore_command_write((25 << 8) | SDCARD_CTRL_RESPONSE_SHORT |
							 (SDCARD_CTRL_DATA_TRANSFER_WRITE << 5));
		sdcore_send_write(1);
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
		sdcore_blocksize_write(BLOCK_SIZE);
		sdcore_blockcount_write(1);
		sdcore_command_write((17 << 8) | SDCARD_CTRL_RESPONSE_SHORT |
							 (SDCARD_CTRL_DATA_TRANSFER_READ << 5));
		sdcore_send_write(1);
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
		sdcore_blocksize_write(BLOCK_SIZE);
		sdcore_blockcount_write(blockcnt);
		sdcore_command_write((18 << 8) | SDCARD_CTRL_RESPONSE_SHORT |
							 (SDCARD_CTRL_DATA_TRANSFER_READ << 5));
		sdcore_send_write(1);
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
	sdcore_send_write(1);
	return sdcard_wait_response();
}

int sdcard_send_status(unsigned int rca) {
#ifdef SDCARD_DEBUG
	printf("CMD13: SEND_STATUS\n");
#endif
	sdcore_argument_write(rca << 16);
	sdcore_command_write((13 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_send_write(1);
	return sdcard_wait_response();
}

int sdcard_set_block_count(unsigned int blockcnt) {
#ifdef SDCARD_DEBUG
	printf("CMD23: SET_BLOCK_COUNT\n");
#endif
	sdcore_argument_write(blockcnt);
	sdcore_command_write((23 << 8) | SDCARD_CTRL_RESPONSE_SHORT);
	sdcore_send_write(1);
	return sdcard_wait_response();
}

void sdcard_decode_cid(void) {
	printf(
		"CID Register: 0x%08x%08x%08x%08x\n"
		"Manufacturer ID: 0x%x\n"
		"Application ID 0x%x\n"
		"Product name: %c%c%c%c%c\n",
			sdcard_response[1],
			sdcard_response[2],
			sdcard_response[3],
			sdcard_response[4],

			(sdcard_response[1] >> 16) & 0xffff,

			sdcard_response[1] & 0xffff,

			(sdcard_response[2] >> 24) & 0xff,
			(sdcard_response[2] >> 16) & 0xff,
			(sdcard_response[2] >>  8) & 0xff,
			(sdcard_response[2] >>  0) & 0xff,
			(sdcard_response[3] >> 24) & 0xff
		);
	int crc = sdcard_response[4] & 0x000000FF;
	int month = (sdcard_response[4] & 0x00000F00) >> 8;
	int year = (sdcard_response[4] & 0x000FF000) >> 12;
	int psn = ((sdcard_response[4] & 0xFF000000) >> 24) | ((sdcard_response[3] & 0x00FFFFFF) << 8);
	printf( "CRC: %02x\n", crc);
	printf( "Production date(m/yy): %d/%d\n", month, year);
	printf( "PSN: %08x\n", psn);
	printf( "OID: %c%c\n", (sdcard_response[1] & 0x00FF0000) >> 16, (sdcard_response[1] & 0x0000FF00) >> 8);
}

void sdcard_decode_csd(void) {
	/* FIXME: only support CSR structure version 2.0 */

	int size = ((sdcard_response[3] & 0xFFFF0000) >> 16) + ((sdcard_response[2] & 0x000000FF) << 16) + 1;
	printf(
		"CSD Register: 0x%x%08x%08x%08x\n"
		"Max data transfer rate: %d MB/s\n"
		"Max read block length: %d bytes\n"
		"Device size: %d GB\n",
			sdcard_response[1],
			sdcard_response[2],
			sdcard_response[3],
			sdcard_response[4],

			(sdcard_response[1] >> 24) & 0xff,

			(1 << ((sdcard_response[2] >> 16) & 0xf)),

			size * BLOCK_SIZE / (1024 * 1024)
	);
}

/* bist */

#ifdef CSR_SDDATAWRITER_BASE
void sdcard_sddatawriter_start(void) {
	sddatawriter_reset_write(1);
	sddatawriter_start_write(1);
}

int sdcard_sddatawriter_wait(void) {
	unsigned check_counter = 0;
	unsigned done = 0;
	while(!done) {
		done = sddatawriter_done_read();
		REPEATED_MSG(++check_counter, CHECK_LOOPS_PRINT_THRESHOLD,
					 "\033[36m  sddatawriter_done_read: %08x (check #%d)",
					 done, ++check_counter);
		if(check_counter > CHECK_LOOPS_PRINT_THRESHOLD) {
			putchar('\n');
			return NO_RESPONSE; //If we reach threshold, and cmdevt didn't return valid status, return NO_RESPONSE
		}
	}
	return 0;
}
#endif

#ifdef CSR_SDDATAREADER_BASE
void sdcard_sddatareader_start(void) {
	sddatareader_reset_write(1);
	sddatareader_start_write(1);
}

int sdcard_sddatareader_wait(void) {
	unsigned check_counter = 0;
	unsigned done = 0;
	while((done & 1) == 0) {
		done = sddatareader_done_read();
		REPEATED_MSG(++check_counter, CHECK_LOOPS_PRINT_THRESHOLD,
					 "\033[36m  sddatareader_done_read: %08x (check #%d)",
					 done, check_counter);
		if(check_counter > CHECK_LOOPS_PRINT_THRESHOLD) {
			putchar('\n');
			return NO_RESPONSE; //If we reach threshold, and cmdevt didn't return valid status, return NO_RESPONSE
		}
	}
	return 0;
}
#endif

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
#ifdef SDCARD_DEBUG
	printf("Accepted voltage: ");
	if(sdcard_response[4] & 0x0)
		printf("Not defined\n");
	else if(sdcard_response[4] >> 8 & 0x1)
		printf("2.7-3.6V\n");
	else if(sdcard_response[4] >> 12 & 0x1)
		printf("Reserved\n");
	else if(sdcard_response[4] >> 16 & 0x1)
		printf("Reserved\n");
	else
		printf("Invalid response\n");
#endif

	/* wait for card to be ready */
	/* FIXME: 1.8v support */
	for(;;) {
		sdcard_app_cmd(0);
		sdcard_app_send_op_cond(1, 0);
		if (sdcard_response[4] & 0x80000000) {
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
	rca = (sdcard_response[4] >> 16) & 0xffff;

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
	sdcard_app_set_blocklen(BLOCK_SIZE);

	return 0;
}

extern void dump_bytes(unsigned int *ptr, int count, unsigned long addr);

void sdcard_test_write(unsigned block, const char *data)
{
#ifdef CSR_SDDATAWRITER_BASE
	const char *c = data;
	int i;
	for(i = 0; i < BLOCK_SIZE; i++) {
		SDWRITE[i] = *c;
		if(*(++c) == 0) {
			c = data;
		}
	}

	printf("SDWRITE:\n");
	dump_bytes((unsigned int *)SDWRITE_BASE, BLOCK_SIZE, (unsigned long) SDWRITE_BASE);

	sdcard_set_block_count(1);
	sdcard_sddatawriter_start();
	sdcard_write_single_block(block * BLOCK_SIZE);
	sdcard_sddatawriter_wait();
	sdcard_stop_transmission();
#else
	printf("Writer core not present\n");
#endif
}

void sdcard_test_read(unsigned block)
{
#ifdef CSR_SDDATAREADER_BASE
	int i;
	for(i = 0; i < sizeof(SDREAD); ++i) {
		SDREAD[i] = 0;
	}
	printf("SDREAD (0x%08x) before read:\n", SDREAD);
	dump_bytes((unsigned int *)SDREAD_BASE, BLOCK_SIZE, (unsigned long) SDREAD_BASE);

	sdcard_set_block_count(1);
	sdcard_sddatareader_start();
	sdcard_read_single_block(block * BLOCK_SIZE);
	sdcard_sddatareader_wait();

	printf("SDREAD (0x%08x) after read:\n", SDREAD);
	dump_bytes((unsigned int *)SDREAD_BASE, BLOCK_SIZE, (unsigned long) SDREAD_BASE);
#else
	printf("Reader core not present\n");
#endif
}

int sdcard_test(unsigned int count)
{
#if defined(CSR_SDDATAREADER_BASE) && defined(CSR_SDDATAWRITER_BASE)
	srand(0);
	int i, j, status;
	int crcerrors = 0;
	int timeouterrors = 0;
	int repeat = 0;

	sdcore_datawcrcclear_write(1);

	for(i = 0; i < count; i = repeat ? i : i + 1) {
		REPEATED_MSG(i, 0, "\033[96mWriting block %d (%d/%d); crc errors: %d; timeouts: %d; datawcrc: %u",
					 i, i + 1, count, crcerrors, timeouterrors, sdcore_datawcrcerrors_read());
		if(!repeat) {
			for(j = 0; j < BLOCK_SIZE; ++j) {
				unsigned number = rand();
				SDWRITE[j] = number & 0xFF;
			}
		} else {
			busy_wait(1);
		}
		repeat = 0;

		sdcard_set_block_count(1);
		sdcard_sddatawriter_start();
		status = sdcard_write_single_block(i * BLOCK_SIZE);
		if (status == SD_CRCERROR) {
			++crcerrors;
		} else if (status == SD_TIMEOUT) {
			++timeouterrors;
		}
		if (status != SD_OK) {
			REPEATED_MSG(1, 0, "\033[31m  Repeating\n");
			repeat = 1;
		}
		status = sdcard_sddatawriter_wait();
		if (status != 0) {
			REPEATED_MSG(1, 0, "\033[31m  Repeating\n");
			repeat = 1;
		}
		sdcard_stop_transmission();
	}
	REPEATED_MSG(i, 0, "\033[39;1mWriting crc errors: %d; timeouts: %d; datawcrc: %u",
				 crcerrors, timeouterrors, sdcore_datawcrcerrors_read());

	srand(0);
	int errors = 0;
	int errorsblk = 0;
	crcerrors = 0;
	timeouterrors = 0;
	for(i = 0; i < count; i = repeat ? i : i + 1) {
		REPEATED_MSG(i, 0, "\033[96mReading and checking block %d (%d/%d); errors: %d in %d blocks; crc errors: %d; timeouts: %d",
					 i, i + 1, count, errors, errorsblk, crcerrors, timeouterrors);

	        repeat = 0;
		sdcard_set_block_count(1);
		sdcard_sddatareader_start();
		status = sdcard_read_single_block(i * BLOCK_SIZE);
		if (status == SD_CRCERROR) {
			++crcerrors;
		} else if (status == SD_TIMEOUT) {
			++timeouterrors;
		}
		if (status != SD_OK) {
			REPEATED_MSG(1, 0, "\033[31m  Repeating\n");
			repeat = 1;
			continue;
		}
		status = sdcard_sddatareader_wait();
		if (status != 0) {
			REPEATED_MSG(1, 0, "\033[31m  Repeating\n");
			repeat = 1;
			continue;
		}

		int ok = 1;
		for(j = 0; j < BLOCK_SIZE; ++j) {
			unsigned number = rand();

			if(SDREAD[j] != (number & 0xFF)) {
				++errors;
				ok = 0;
			}
		}
		if(!ok) {
			REPEATED_MSG(0, 0, "\033[31m  Block check failed\n");
			++errorsblk;
		}
	}
	REPEATED_MSG(i, 0, "\033[39;1mReading errors: %d in %d blocks; crc errors: %d; timeouts: %d",
				 errors, errorsblk, crcerrors, timeouterrors);
#else
	printf("Reader and/or writer core not present\n");
#endif
	return 0;
}
#endif /* CSR_SDCORE_BASE */
