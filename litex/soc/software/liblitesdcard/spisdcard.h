// This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
// This file is Copyright (c) 2020 Rob Shelton <rob.s.ng15@googlemail.com>
// License: BSD

#ifndef __SPISDCARD_H
#define __SPISDCARD_H

#ifdef __cplusplus
extern "C" {
#endif

#include <generated/csr.h>

#ifdef CSR_SPISDCARD_BASE

/*-----------------------------------------------------------------------*/
/* SPI Master Flags                                                      */
/*-----------------------------------------------------------------------*/

#define SPI_CS_HIGH (0 << 0)
#define SPI_CS_LOW  (1 << 0)
#define SPI_START   (1 << 0)
#define SPI_DONE    (1 << 0)
#define SPI_LENGTH  (1 << 8)

/*-----------------------------------------------------------------------*/
/* SPI SDCard Commands                                                   */
/*-----------------------------------------------------------------------*/

#define CMD0    (0)         /* GO_IDLE_STATE */
#define CMD1    (1)         /* SEND_OP_COND */
#define ACMD41  (0x80 + 41) /* SEND_OP_COND (SDC) */
#define CMD8    (8)         /* SEND_IF_COND */
#define CMD9    (9)         /* SEND_CSD */
#define CMD10   (10)        /* SEND_CID */
#define CMD12   (12)        /* STOP_TRANSMISSION */
#define CMD13   (13)        /* SEND_STATUS */
#define ACMD13  (0x80 + 13) /* SD_STATUS (SDC) */
#define CMD16   (16)        /* SET_BLOCKLEN */
#define CMD17   (17)        /* READ_SINGLE_BLOCK */
#define CMD18   (18)        /* READ_MULTIPLE_BLOCK */
#define CMD23   (23)        /* SET_BLOCK_COUNT */
#define ACMD23  (0x80 + 23) /* SET_WR_BLK_ERASE_COUNT (SDC) */
#define CMD24   (24)        /* WRITE_BLOCK */
#define CMD25   (25)        /* WRITE_MULTIPLE_BLOCK */
#define CMD32   (32)        /* ERASE_ER_BLK_START */
#define CMD33   (33)        /* ERASE_ER_BLK_END */
#define CMD38   (38)        /* ERASE */
#define CMD55   (55)        /* APP_CMD */
#define CMD58   (58)        /* READ_OCR */

/*-----------------------------------------------------------------------*/
/* SPI SDCard User functions                                             */
/*-----------------------------------------------------------------------*/

uint8_t spisdcard_init(void);
void fatfs_set_ops_spisdcard(void);

#endif /* CSR_SPISDCARD_BASE */

#ifdef __cplusplus
}
#endif

#endif /* __SPISDCARD_H */
