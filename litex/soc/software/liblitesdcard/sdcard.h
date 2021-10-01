// This file is Copyright (c) 2017 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD

#ifndef __SDCARD_H
#define __SDCARD_H

#include <generated/csr.h>

#define CLKGEN_STATUS_BUSY		0x1
#define CLKGEN_STATUS_PROGDONE	0x2
#define CLKGEN_STATUS_LOCKED	0x4

#ifdef CSR_SDCORE_BASE

#define SD_CMD_RESPONSE_SIZE 16

#define SD_OK         0
#define SD_CRCERROR   1
#define SD_TIMEOUT    2
#define SD_WRITEERROR 3

#define SD_SWITCH_CHECK  0
#define SD_SWITCH_SWITCH 1

#define SD_SPEED_SDR12  0
#define SD_SPEED_SDR25  1
#define SD_SPEED_SDR50  2
#define SD_SPEED_SDR104 3
#define SD_SPEED_DDR50  4

#define SD_DRIVER_STRENGTH_B 0
#define SD_DRIVER_STRENGTH_A 1
#define SD_DRIVER_STRENGTH_C 2
#define SD_DRIVER_STRENGTH_D 3

#define SD_GROUP_ACCESSMODE     0
#define SD_GROUP_COMMANDSYSTEM  1
#define SD_GROUP_DRIVERSTRENGTH 2
#define SD_GROUP_POWERLIMIT     3

#define SDCARD_STREAM_STATUS_OK           0b000
#define SDCARD_STREAM_STATUS_TIMEOUT      0b001
#define SDCARD_STREAM_STATUS_DATAACCEPTED 0b010
#define SDCARD_STREAM_STATUS_CRCERROR     0b101
#define SDCARD_STREAM_STATUS_WRITEERROR   0b110

#define SDCARD_CTRL_DATA_TRANSFER_NONE  0
#define SDCARD_CTRL_DATA_TRANSFER_READ  1
#define SDCARD_CTRL_DATA_TRANSFER_WRITE 2

#define SDCARD_CTRL_RESPONSE_NONE       0
#define SDCARD_CTRL_RESPONSE_SHORT      1
#define SDCARD_CTRL_RESPONSE_LONG       2
#define SDCARD_CTRL_RESPONSE_SHORT_BUSY 3

/*-----------------------------------------------------------------------*/
/* SDCard command helpers                                                */
/*-----------------------------------------------------------------------*/

int sdcard_wait_cmd_done(void);
int sdcard_wait_data_done(void);
int sdcard_wait_response(void);

/*-----------------------------------------------------------------------*/
/* SDCard clocker functions                                              */
/*-----------------------------------------------------------------------*/

void sdcard_set_clk_freq(unsigned long clk_freq, int show);

/*-----------------------------------------------------------------------*/
/* SDCard commands functions                                             */
/*-----------------------------------------------------------------------*/

int sdcard_go_idle(void);
int sdcard_send_ext_csd(void);
int sdcard_app_cmd(uint16_t rca);
int sdcard_app_send_op_cond(int hcs);
int sdcard_all_send_cid(void);
int sdcard_set_relative_address(void);

int sdcard_send_cid(uint16_t rca);
int sdcard_send_csd(uint16_t rca);
int sdcard_select_card(uint16_t rca);
int sdcard_app_set_bus_width(void);
int sdcard_switch(unsigned int mode, unsigned int group, unsigned int value);
int sdcard_app_send_scr(void);
int sdcard_app_set_blocklen(unsigned int blocklen);
int sdcard_write_single_block(unsigned int blockaddr);
int sdcard_write_multiple_block(unsigned int blockaddr, unsigned int blockcnt);
int sdcard_read_single_block(unsigned int blockaddr);
int sdcard_read_multiple_block(unsigned int blockaddr, unsigned int blockcnt);
int sdcard_stop_transmission(void);
int sdcard_send_status(uint16_t rca);
int sdcard_set_block_count(unsigned int blockcnt);
uint16_t sdcard_decode_rca(void);
void sdcard_decode_cid(void);
void sdcard_decode_csd(void);

/*-----------------------------------------------------------------------*/
/* SDCard user functions                                                 */
/*-----------------------------------------------------------------------*/

int sdcard_init(void);
void sdcard_read(uint32_t sector, uint32_t count, uint8_t* buf);
void sdcard_write(uint32_t sector, uint32_t count, uint8_t* buf);

#endif /* CSR_SDCORE_BASE */

#endif /* __SDCARD_H */
