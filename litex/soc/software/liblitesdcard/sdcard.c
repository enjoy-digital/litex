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

#include "sdcard.h"

#define SDCARD_DEBUG

#ifdef CSR_SDCORE_BASE

unsigned int sdcard_response[SD_RESPONSE_SIZE/4];

volatile char *sdread_buf  = (char*)(SDREAD_BASE);
volatile char *sdwrite_buf = (char*)(SDWRITE_BASE);

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

	printf("Setting SDCard clk freq to %dMHz\n", freq);
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

	printf("Setting SDCard clk freq to %dMHz\n", freq);
	sdclk_get_config(1000*freq, &clk_m, &clk_d);
	sdclk_set_config(clk_m, clk_d);
}

#else

void sdclk_set_clk(unsigned int freq) {
	printf("No SDClocker, returning.\n");
}

#endif

/* command utils */

int sdcard_wait_cmd_done(void) {
	unsigned int cmdevt;
	while (1) {
		cmdevt = sdcore_cmdevt_read();
		busy_wait(5); /* FIXME */
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
		busy_wait(5); /* FIXME */
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

	csr_rd_buf_uint32(CSR_SDCORE_RESPONSE_ADDR, sdcard_response, SD_RESPONSE_SIZE/4);

#ifdef SDCARD_DEBUG
	for(i = 0; i < SD_RESPONSE_SIZE/4; i++) {
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
		sdcore_blocksize_write(SD_BLOCK_SIZE);
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
		sdcore_blocksize_write(SD_BLOCK_SIZE);
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
		sdcore_blocksize_write(SD_BLOCK_SIZE);
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
		sdcore_blocksize_write(SD_BLOCK_SIZE);
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

			size * SD_BLOCK_SIZE / (1024 * 1024)
	);
}

/* writer / reader */

#ifdef CSR_SDDATAWRITER_BASE

void sdcard_sddatawriter_start(void) {
	sddatawriter_reset_write(1);
	sddatawriter_start_write(1);
}

int sdcard_sddatawriter_wait(void) {
	unsigned done = 0;
	while(!done) {
		done = sddatawriter_done_read();
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
	unsigned done = 0;
	while((done & 1) == 0) {
		done = sddatareader_done_read();
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
	sdcard_decode_cid();

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
	sdcard_app_set_blocklen(SD_BLOCK_SIZE);

	return 0;
}

extern void dump_bytes(unsigned int *ptr, int count, unsigned long addr);

void sdcard_write(unsigned block, const char *data, char silent)
{
#ifdef CSR_SDDATAWRITER_BASE
	const char *c = data;
	int i;

	if (data != NULL) {
		for(i=0; i<SD_BLOCK_SIZE; i++) {
			sdwrite_buf[i] = *c;
			if(*(++c) == 0) {
				c = data;
			}
		}
	}
	if (silent == 0) {
		printf("Writing SD block %d from mem:\n", block);
		dump_bytes((unsigned int *)SDWRITE_BASE, SD_BLOCK_SIZE, (unsigned long) SDWRITE_BASE);
	}

	sdcore_datawcrcclear_write(1);
	sdcard_set_block_count(1);
	sdcard_sddatawriter_start();
	sdcard_write_single_block(block * SD_BLOCK_SIZE);
	sdcard_sddatawriter_wait();
	sdcard_stop_transmission();
#else
	printf("No SDWriter, returning.\n");
#endif
}

void sdcard_read(unsigned block, char silent)
{
#ifdef CSR_SDDATAREADER_BASE
	int i;
	for(i = 0; i < sizeof(sdread_buf); ++i) {
		sdread_buf[i] = 0;
	}
	if (silent == 0)
		printf("Reading SD block %d from mem:\n", block);

	sdcard_set_block_count(1);
	sdcard_sddatareader_start();
	sdcard_read_single_block(block * SD_BLOCK_SIZE);
	sdcard_sddatareader_wait();

	if (silent == 0)
		dump_bytes((unsigned int *)SDREAD_BASE, SD_BLOCK_SIZE, (unsigned long) SDREAD_BASE);
#else
	printf("No SDReader, returning.\n");
#endif
}

int sdcard_test(unsigned int blocks)
{
#if defined(CSR_SDDATAREADER_BASE) && defined(CSR_SDDATAWRITER_BASE)
	int i, j;
	int errors;

	printf("Test SDCard on %d blocks...\n", blocks);
	errors = 0;
	for(i=0; i<blocks; i=i+1) {
		/* fill write mem */
		srand(0);
		for(j=0; j<SD_BLOCK_SIZE; j++)
			sdwrite_buf[j] = (rand() + i) & 0xff;
		/* write block from write mem */
		sdcard_write(i, NULL, 0);

		busy_wait(100); /* FIXME */

		/* read block to read mem */
		sdcard_read(i, 0);
		/* check read mem */
		srand(0);
		for(j=0; j<SD_BLOCK_SIZE; j++)
			if (sdread_buf[j] != ((rand() + i) & 0xff))
				errors++;
	}
	printf("Errors: %d\n", errors);
	return errors;
#else
	printf("No SDWriter or SDReader, returning.\n");
#endif
	return 0;
}

// Return values
#define SUCCESS         0x01
#define FAILURE         0x00

// READSECTOR
//      Read a 512 byte sector from the SD CARD
//      Given SECTORNUMBER and memory STORAGE
//
//      Sequence
//          Send CMD17 - Read Block
//          Command Sequence is DUMMY=0xff CMD17=0x51 SECTORNUMBER (32bit UNSIGNED as bits 32-25,24-17, 16-9, 8-1) CRC=0xff
//          Wait for SD CARD to send 0x00 indicating SD CARD is processing
//          Wait for SD CARD to send 0xfe indicating SD CARD BLOCK START
//          Read 512 bytes
//          Read 8 DUMMY bytes
//      Return 0 success, 1 failure
//
//      Details from https://openlabpro.com/guide/interfacing-microcontrollers-with-sd-card/ section "Read/Write SD Card"
uint8_t readSector(uint32_t sectorNumber, uint8_t *storage);
uint8_t readSector(uint32_t sectorNumber, uint8_t *storage)
{
	int n;

	// FIXME: handle errors.

	sdcard_read(sectorNumber, 1);
	 for(n=0; n<512; n++)
        storage[n] = sdread_buf[n];

    return SUCCESS;
}

// FAT16 Specific code starts here
// Details from https://codeandlife.com/2012/04/02/simple-fat-and-sd-tutorial-part-1/

// Structure to store SD CARD partition table
typedef struct {
    uint8_t first_byte;
    uint8_t start_chs[3];
    uint8_t partition_type;
    uint8_t end_chs[3];
    uint32_t start_sector;
    uint32_t length_sectors;
} __attribute((packed)) PartitionTable;

PartitionTable sdCardPartition;

// Structure to store SD CARD FAT16 Boot Sector (boot code is ignored, provides layout of the FAT16 partition on the SD CARD)
typedef struct {
    uint8_t jmp[3];
    uint8_t oem[8];
    uint16_t sector_size;
    uint8_t sectors_per_cluster;
    uint16_t reserved_sectors;
    uint8_t number_of_fats;
    uint16_t root_dir_entries;
    uint16_t total_sectors_short; // if zero, later field is used
    uint8_t media_descriptor;
    uint16_t fat_size_sectors;
    uint16_t sectors_per_track;
    uint16_t number_of_heads;
    uint32_t hidden_sectors;
    uint32_t total_sectors_long;

    uint8_t drive_number;
    uint8_t current_head;
    uint8_t boot_signature;
    uint32_t volume_id;
    uint8_t volume_label[11];
    uint8_t fs_type[8];
    uint8_t boot_code[448];
    uint16_t boot_sector_signature;
} __attribute((packed)) Fat16BootSector;

Fat16BootSector sdCardFatBootSector;

// Structure to store SD CARD FAT16 Root Directory Entries
//      Allocated to MAIN RAM - hence pointer
typedef struct {
    uint8_t filename[8];
    uint8_t ext[3];
    uint8_t attributes;
    uint8_t reserved[10];
    uint16_t modify_time;
    uint16_t modify_date;
    uint16_t starting_cluster;
    uint32_t file_size;
} __attribute((packed)) Fat16Entry;

Fat16Entry *sdCardFat16RootDir;

// Structure to store SD CARD FAT16 Entries
//      Array of uint16_tS (16bit integers)
uint16_t *sdCardFatTable;

// Calculated sector numbers on the SD CARD for the FAT16 Entries and ROOT DIRECTORY
uint32_t fatSectorStart, rootDirSectorStart;

// Storage for SECTOR read from SD CARD
uint8_t sdCardSector[512];

// SPI_SDCARD_READMBR
//      Function exposed to BIOS to retrieve FAT16 partition details, FAT16 Entry Table, FAT16 Root Directory
//      MBR = Master Boot Record - Sector 0x00000000 on SD CARD - Contains Partition 1 details at 0x1be
//
// FIXME only checks partition 1 out of 4
//
//      Return 0 success, 1 failure
//
// Details from https://codeandlife.com/2012/04/02/simple-fat-and-sd-tutorial-part-1/
uint8_t spi_sdcard_readMBR(void)
{
    int i, n;

    // Read Sector 0x00000000
    printf("Reading MBR\n");
    if( readSector(0x00000000, sdCardSector)==SUCCESS ) {
        // Copy Partition 1 Entry from byte 0x1be
        // FIXME should check 0x55 0xaa at end of sector
        memcpy(&sdCardPartition, &sdCardSector[0x1be], sizeof(PartitionTable));

        // Check Partition 1 is valid, FIRST_BYTE=0x00 or 0x80
        // Check Partition 1 has type 4, 6 or 14 (FAT16 of various sizes)
        printf("Partition 1 Information: Active=0x%02x, Type=0x%02x, LBAStart=0x%08x\n", sdCardPartition.first_byte, sdCardPartition.partition_type, sdCardPartition.start_sector);
        if( (sdCardPartition.first_byte!=0x80) && (sdCardPartition.first_byte!=0x00) ) {
            printf("Partition 1 Not Valid\n");
            return FAILURE;
        }
        if( (sdCardPartition.partition_type==4) || (sdCardPartition.partition_type==6) || (sdCardPartition.partition_type==14) ) {
            printf("Partition 1 is FAT16\n");
        }
        else {
            printf("Partition 1 Not FAT16\n");
            return FAILURE;
        }
    }
    else {
        printf("Failed to read MBR\n");
        return FAILURE;
    }

    // Read Parition 1 Boot Sector - Found from Partion Table
    printf("\nRead FAT16 Boot Sector\n");
    sdCardPartition.start_sector = sdCardPartition.start_sector/512;
    if( readSector(sdCardPartition.start_sector, sdCardSector)==SUCCESS ) {
        memcpy(&sdCardFatBootSector, &sdCardSector, sizeof(Fat16BootSector));
    }
    else {
        printf("Failed to read FAT16 Boot Sector\n");
        return FAILURE;
    }

    // Print details of Parition 1
    printf("  Jump Code:              0x%02x 0x%02x 0x%02x\n",sdCardFatBootSector.jmp[0],sdCardFatBootSector.jmp[1],sdCardFatBootSector.jmp[2]);
    printf("  OEM Code:               [");
    for(n=0; n<8; n++)
        printf("%c",sdCardFatBootSector.oem[n]);
    printf("]\n");
    printf("  Sector Size:            %d\n",sdCardFatBootSector.sector_size);
    printf("  Sectors Per Cluster:    %d\n",sdCardFatBootSector.sectors_per_cluster);
    printf("  Reserved Sectors:       %d\n",sdCardFatBootSector.reserved_sectors);
    printf("  Number of Fats:         %d\n",sdCardFatBootSector.number_of_fats);
    printf("  Root Dir Entries:       %d\n",sdCardFatBootSector.root_dir_entries);
    printf("  Total Sectors Short:    %d\n",sdCardFatBootSector.total_sectors_short);
    printf("  Media Descriptor:       0x%02x\n",sdCardFatBootSector.media_descriptor);
    printf("  Fat Size Sectors:       %d\n",sdCardFatBootSector.fat_size_sectors);
    printf("  Sectors Per Track:      %d\n",sdCardFatBootSector.sectors_per_track);
    printf("  Number of Heads:        %d\n",sdCardFatBootSector.number_of_heads);
    printf("  Hidden Sectors:         %d\n",sdCardFatBootSector.hidden_sectors);
    printf("  Total Sectors Long:     %d\n",sdCardFatBootSector.total_sectors_long);
    printf("  Drive Number:           0x%02x\n",sdCardFatBootSector.drive_number);
    printf("  Current Head:           0x%02x\n",sdCardFatBootSector.current_head);
    printf("  Boot Signature:         0x%02x\n",sdCardFatBootSector.boot_signature);
    printf("  Volume ID:              0x%08x\n",sdCardFatBootSector.volume_id);
    printf("  Volume Label:           [");
    for(n=0; n<11; n++)
        printf("%c",sdCardFatBootSector.volume_label[n]);
    printf("]\n");
     printf("  Volume Label:           [");
    for(n=0; n<8; n++)
        printf("%c",sdCardFatBootSector.fs_type[n]);
    printf("]\n");
    printf("  Boot Sector Signature:  0x%04x\n\n",sdCardFatBootSector.boot_sector_signature);

    // Check Partition 1 is valid, not 0 length
    if(sdCardFatBootSector.total_sectors_long==0) {
        printf("Error reading FAT16 Boot Sector\n");
        return FAILURE;
    }

    // Read in FAT16 File Allocation Table, array of 16bit unsinged integers
    // Calculate Storage from TOP of MAIN RAM
    sdCardFatTable = (uint16_t *)(MAIN_RAM_BASE+MAIN_RAM_SIZE-sdCardFatBootSector.sector_size*sdCardFatBootSector.fat_size_sectors);
    printf("sdCardFatTable = 0x%08x  Reading Fat16 Table (%d Sectors Long)\n\n",sdCardFatTable,sdCardFatBootSector.fat_size_sectors);

    // Calculate Start of FAT16 File Allocation Table (start of partition plus reserved sectors)
    fatSectorStart=sdCardPartition.start_sector+sdCardFatBootSector.reserved_sectors;
    for(n=0; n<sdCardFatBootSector.fat_size_sectors; n++) {
        if( readSector(fatSectorStart+n, (uint8_t *)((uint8_t*)sdCardFatTable)+sdCardFatBootSector.sector_size*n)==FAILURE ) {
            printf("Error reading FAT16 table - sector %d\n",n);
            return FAILURE;
        }
    }

    // Read in FAT16 Root Directory
    // Calculate Storage from TOP of MAIN RAM
    sdCardFat16RootDir= (Fat16Entry *)(MAIN_RAM_BASE+MAIN_RAM_SIZE-sdCardFatBootSector.sector_size*sdCardFatBootSector.fat_size_sectors-sdCardFatBootSector.root_dir_entries*sizeof(Fat16Entry));
    printf("sdCardFat16RootDir = 0x%08x  Reading Root Directory (%d Sectors Long)\n\n",sdCardFat16RootDir,sdCardFatBootSector.root_dir_entries*sizeof(Fat16Entry)/sdCardFatBootSector.sector_size);

    // Calculate Start of FAT ROOT DIRECTORY (start of partition plues reserved sectors plus size of File Allocation Table(s))
    rootDirSectorStart=sdCardPartition.start_sector+sdCardFatBootSector.reserved_sectors+sdCardFatBootSector.number_of_fats*sdCardFatBootSector.fat_size_sectors;
    for(n=0; n<sdCardFatBootSector.root_dir_entries*sizeof(Fat16Entry)/sdCardFatBootSector.sector_size; n++) {
        if( readSector(rootDirSectorStart+n, (uint8_t *)(sdCardFatBootSector.sector_size*n+(uint8_t *)(sdCardFat16RootDir)))==FAILURE ) {
            printf("Error reading Root Dir - sector %d\n",n);
            return FAILURE;
        }
    }

    // Print out Root Directory
    // Alternates between valid and invalid directory entries for SIMPLE 8+3 file names, extended filenames in other entries
    // Only print valid characters
    printf("\nRoot Directory\n");
    for(n=0; n<sdCardFatBootSector.root_dir_entries; n++) {
        if( (sdCardFat16RootDir[n].filename[0]!=0) && (sdCardFat16RootDir[n].file_size>0)) {
            printf("  File %d [",n);
            for( i=0; i<8; i++) {
                if( (sdCardFat16RootDir[n].filename[i]>31) && (sdCardFat16RootDir[n].filename[i]<127) )
                    printf("%c",sdCardFat16RootDir[n].filename[i]);
                else
                    printf(" ");
            }
            printf(".");
            for( i=0; i<3; i++) {
                 if( (sdCardFat16RootDir[n].ext[i]>31) && (sdCardFat16RootDir[n].ext[i]<127) )
                    printf("%c",sdCardFat16RootDir[n].ext[i]);
                else
                    printf(" ");
            }
            printf("] @ Cluster %d for %d bytes\n",sdCardFat16RootDir[n].starting_cluster,sdCardFat16RootDir[n].file_size);
        }
    }

    printf("\n");
    return SUCCESS;
}

// SPI_SDCARD_READFILE
//      Function exposed to BIOS to retrieve FILENAME+EXT into ADDRESS
//
// FIXME only checks UPPERCASE 8+3 filenames
//
//      Return 0 success, 1 failure
//
// Details from https://codeandlife.com/2012/04/02/simple-fat-and-sd-tutorial-part-1/
uint8_t spi_sdcard_readFile(char *filename, char *ext, unsigned long address)
{
    int i, n, sector;
    uint16_t fileClusterStart;
    uint32_t fileLength, bytesRemaining, clusterSectorStart;
    uint16_t nameMatch;
    printf("Reading File [%s.%s] into 0x%08x : ",filename, ext, address);

    // Find FILENAME+EXT in Root Directory
    // Indicate FILE found by setting the starting cluster number
    fileClusterStart=0; n=0;
    while( (fileClusterStart==0) && (n<sdCardFatBootSector.root_dir_entries) ) {
        nameMatch=0;
        if( sdCardFat16RootDir[n].filename[0]!=0 ) {
            nameMatch=1;
            for(i=0; i<strlen(filename); i++)
                if(sdCardFat16RootDir[n].filename[i]!=filename[i]) nameMatch=0;
            for(i=0; i<strlen(ext); i++)
                if(sdCardFat16RootDir[n].ext[i]!=ext[i]) nameMatch=0;
        }

        if(nameMatch==1) {
            fileClusterStart=sdCardFat16RootDir[n].starting_cluster;
            fileLength=sdCardFat16RootDir[n].file_size;
        } else {
            n++;
        }
    }

    // If starting cluster number is still 0 then file not found
    if(fileClusterStart==0) {
        printf("File not found\n");
        return FAILURE;
    }

    printf("File starts at Cluster %d length %d\n",fileClusterStart,fileLength);

    // ZERO Length file are automatically assumed to have been read SUCCESS
    if( fileLength==0 ) return SUCCESS;

    // Read each cluster sector by sector, i being number of clusters
    bytesRemaining=fileLength;
    // Calculate number of clusters (always >1)
    for(i=0; i<1+((fileLength/sdCardFatBootSector.sectors_per_cluster)/sdCardFatBootSector.sector_size); i++) {
        printf("\rCluster: %d",fileClusterStart);

        // Locate start of cluster on SD CARD and read appropraite number of sectors
        clusterSectorStart=rootDirSectorStart+(fileClusterStart-1)*sdCardFatBootSector.sectors_per_cluster;
        for(sector=0; sector<sdCardFatBootSector.sectors_per_cluster; sector++) {
            // Read Sector from SD CARD
            // If whole sector to be read, read directly into memory
            // Otherwise, read to sdCardSector buffer and transfer appropriate number of bytes
            if(bytesRemaining>sdCardFatBootSector.sector_size) {
                if( readSector(clusterSectorStart+sector,(uint8_t *)address) == FAILURE ) {
                    printf("\nRead Error\n");
                    return FAILURE;
                }
                bytesRemaining=bytesRemaining-sdCardFatBootSector.sector_size;
                address=address+sdCardFatBootSector.sector_size;
            } else {
                if( readSector(clusterSectorStart+sector,sdCardSector) == FAILURE ) {
                    printf("\nRead Error\n");
                    return FAILURE;
                }
                memcpy((uint8_t *)address, sdCardSector, bytesRemaining);
                bytesRemaining=0;
            }
        }

        // Move to next cluster
        fileClusterStart=sdCardFatTable[fileClusterStart];
    }
    printf("\n\n");
    return SUCCESS;
}

#endif /* CSR_SDCORE_BASE */
