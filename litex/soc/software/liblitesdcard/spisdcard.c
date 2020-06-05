// This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
// This file is Copyright (c) 2020 Rob Shelton <rob.s.ng15@googlemail.com>
// License: BSD
// FatFs's generic example adapted for LiteX's SPIMaster.

/*------------------------------------------------------------------------/
/  Foolproof MMCv3/SDv1/SDv2 (in SPI mode) control module
/-------------------------------------------------------------------------/
/
/  Copyright (C) 2019, ChaN, all right reserved.
/
/ * This software is a free software and there is NO WARRANTY.
/ * No restriction on use. You can use, modify and redistribute it for
/   personal, non-profit or commercial products UNDER YOUR RESPONSIBILITY.
/ * Redistributions of source code must retain the above copyright notice.
/
/-------------------------------------------------------------------------*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <generated/csr.h>
#include <generated/mem.h>
#include <system.h>

#include "ff.h"
#include "diskio.h"
#include "spisdcard.h"

#ifdef CSR_SPISDCARD_BASE

/* SPI Master flags */

#define SPI_CS_HIGH (0 << 0)
#define SPI_CS_LOW  (1 << 0)
#define SPI_START   (1 << 0)
#define SPI_DONE    (1 << 0)
#define SPI_LENGTH  (1 << 8)

/* SPI Master low-level functions */

static void spi_set_clk_freq(uint32_t clk_freq) {
    uint32_t divider;
    divider = CONFIG_CLOCK_FREQUENCY/clk_freq + 1;
    printf("divider: %d\n", divider);
    if (divider >= 65535) /* 16-bit hardware divider */
        divider = 65535;
    if (divider <= 2)     /* At least half CPU speed */
        divider = 2;
    printf("Setting SDCard clk freq to ");
    if (clk_freq > 1000000)
        printf("%d MHz\n", (CONFIG_CLOCK_FREQUENCY/divider)/1000000);
    else
        printf("%d KHz\n", (CONFIG_CLOCK_FREQUENCY/divider)/1000);
    spisdcard_clk_divider_write(divider);
}

static uint8_t spi_xfer(uint8_t byte) {
    /* Write byte on MOSI */
    spisdcard_mosi_write(byte);
    /* Initiate SPI Xfer */
    spisdcard_control_write(8*SPI_LENGTH | SPI_START);
    /* Wait SPI Xfer to be done */
    while(spisdcard_status_read() != SPI_DONE);
    /* Read MISO and return it */
    return spisdcard_miso_read();
}

/*--------------------------------------------------------------------------

   Module Private Functions

---------------------------------------------------------------------------*/

/* MMC/SD command (SPI mode) */
#define CMD0    (0)         /* GO_IDLE_STATE */
#define CMD1    (1)         /* SEND_OP_COND */
#define ACMD41  (0x80+41)   /* SEND_OP_COND (SDC) */
#define CMD8    (8)         /* SEND_IF_COND */
#define CMD9    (9)         /* SEND_CSD */
#define CMD10   (10)        /* SEND_CID */
#define CMD12   (12)        /* STOP_TRANSMISSION */
#define CMD13   (13)        /* SEND_STATUS */
#define ACMD13  (0x80+13)   /* SD_STATUS (SDC) */
#define CMD16   (16)        /* SET_BLOCKLEN */
#define CMD17   (17)        /* READ_SINGLE_BLOCK */
#define CMD18   (18)        /* READ_MULTIPLE_BLOCK */
#define CMD23   (23)        /* SET_BLOCK_COUNT */
#define ACMD23  (0x80+23)   /* SET_WR_BLK_ERASE_COUNT (SDC) */
#define CMD24   (24)        /* WRITE_BLOCK */
#define CMD25   (25)        /* WRITE_MULTIPLE_BLOCK */
#define CMD32   (32)        /* ERASE_ER_BLK_START */
#define CMD33   (33)        /* ERASE_ER_BLK_END */
#define CMD38   (38)        /* ERASE */
#define CMD55   (55)        /* APP_CMD */
#define CMD58   (58)        /* READ_OCR */

static
DSTATUS Stat = STA_NOINIT;  /* Disk status */

static
BYTE CardType;          /* b0:MMC, b1:SDv1, b2:SDv2, b3:Block addressing */

/*-----------------------------------------------------------------------*/
/* Transmit bytes to the card                                            */
/*-----------------------------------------------------------------------*/

static
void xmit_mmc (
    const BYTE* buff,   /* Data to be sent */
    UINT bc             /* Number of bytes to send */
)
{
    BYTE d;


    do {
        d = *buff++;    /* Get a byte to be sent */
        spi_xfer(d);
    } while (--bc);
}



/*-----------------------------------------------------------------------*/
/* Receive bytes from the card                                           */
/*-----------------------------------------------------------------------*/

static
void rcvr_mmc (
    BYTE *buff, /* Pointer to read buffer */
    UINT bc     /* Number of bytes to receive */
)
{
    BYTE r;

    do {
        r = spi_xfer(0xff);
        *buff++ = r;            /* Store a received byte */
    } while (--bc);
}



/*-----------------------------------------------------------------------*/
/* Wait for card ready                                                   */
/*-----------------------------------------------------------------------*/

static
int wait_ready (void)   /* 1:OK, 0:Timeout */
{
    BYTE d;
    UINT tmr;


    for (tmr = 5000; tmr; tmr--) {  /* Wait for ready in timeout of 500ms */
        rcvr_mmc(&d, 1);
        if (d == 0xFF) break;
    }

    return tmr ? 1 : 0;
}



/*-----------------------------------------------------------------------*/
/* Deselect the card and release SPI bus                                 */
/*-----------------------------------------------------------------------*/

static
void deselect (void)
{
    BYTE d;

    spisdcard_cs_write(SPI_CS_HIGH); /* Set CS# high */
    rcvr_mmc(&d, 1);    /* Dummy clock (force DO hi-z for multiple slave SPI) */
}



/*-----------------------------------------------------------------------*/
/* Select the card and wait for ready                                    */
/*-----------------------------------------------------------------------*/

static
int select (void)   /* 1:OK, 0:Timeout */
{
    BYTE d;

    spisdcard_cs_write(SPI_CS_LOW); /* Set CS# high */
    rcvr_mmc(&d, 1);    /* Dummy clock (force DO enabled) */
    if (wait_ready()) return 1; /* Wait for card ready */

    deselect();
    return 0;           /* Failed */
}



/*-----------------------------------------------------------------------*/
/* Receive a data packet from the card                                   */
/*-----------------------------------------------------------------------*/

static
int rcvr_datablock (    /* 1:OK, 0:Failed */
    BYTE *buff,         /* Data buffer to store received data */
    UINT btr            /* Byte count */
)
{
    BYTE d[2];
    UINT tmr;


    for (tmr = 1000; tmr; tmr--) {  /* Wait for data packet in timeout of 100ms */
        rcvr_mmc(d, 1);
        if (d[0] != 0xFF) break;
    }
    if (d[0] != 0xFE) return 0;     /* If not valid data token, return with error */

    rcvr_mmc(buff, btr);            /* Receive the data block into buffer */
    rcvr_mmc(d, 2);                 /* Discard CRC */

    return 1;                       /* Return with success */
}



/*-----------------------------------------------------------------------*/
/* Send a data packet to the card                                        */
/*-----------------------------------------------------------------------*/

static
int xmit_datablock (    /* 1:OK, 0:Failed */
    const BYTE *buff,   /* 512 byte data block to be transmitted */
    BYTE token          /* Data/Stop token */
)
{
    BYTE d[2];


    if (!wait_ready()) return 0;

    d[0] = token;
    xmit_mmc(d, 1);             /* Xmit a token */
    if (token != 0xFD) {        /* Is it data token? */
        xmit_mmc(buff, 512);    /* Xmit the 512 byte data block to MMC */
        rcvr_mmc(d, 2);         /* Xmit dummy CRC (0xFF,0xFF) */
        rcvr_mmc(d, 1);         /* Receive data response */
        if ((d[0] & 0x1F) != 0x05)  /* If not accepted, return with error */
            return 0;
    }

    return 1;
}



/*-----------------------------------------------------------------------*/
/* Send a command packet to the card                                     */
/*-----------------------------------------------------------------------*/

static
BYTE send_cmd (     /* Returns command response (bit7==1:Send failed)*/
    BYTE cmd,       /* Command byte */
    DWORD arg       /* Argument */
)
{
    BYTE n, d, buf[6];


    if (cmd & 0x80) {   /* ACMD<n> is the command sequense of CMD55-CMD<n> */
        cmd &= 0x7F;
        n = send_cmd(CMD55, 0);
        if (n > 1) return n;
    }

    /* Select the card and wait for ready except to stop multiple block read */
    if (cmd != CMD12) {
        deselect();
        if (!select()) return 0xFF;
    }

    /* Send a command packet */
    buf[0] = 0x40 | cmd;            /* Start + Command index */
    buf[1] = (BYTE)(arg >> 24);     /* Argument[31..24] */
    buf[2] = (BYTE)(arg >> 16);     /* Argument[23..16] */
    buf[3] = (BYTE)(arg >> 8);      /* Argument[15..8] */
    buf[4] = (BYTE)arg;             /* Argument[7..0] */
    n = 0x01;                       /* Dummy CRC + Stop */
    if (cmd == CMD0) n = 0x95;      /* (valid CRC for CMD0(0)) */
    if (cmd == CMD8) n = 0x87;      /* (valid CRC for CMD8(0x1AA)) */
    buf[5] = n;
    xmit_mmc(buf, 6);

    /* Receive command response */
    if (cmd == CMD12) rcvr_mmc(&d, 1);  /* Skip a stuff byte when stop reading */
    n = 10;                             /* Wait for a valid response in timeout of 10 attempts */
    do
        rcvr_mmc(&d, 1);
    while ((d & 0x80) && --n);

    return d;           /* Return with the response value */
}



/*--------------------------------------------------------------------------

   Public Functions

---------------------------------------------------------------------------*/


/*-----------------------------------------------------------------------*/
/* Get Disk Status                                                       */
/*-----------------------------------------------------------------------*/

DSTATUS disk_status (
    BYTE drv            /* Drive number (always 0) */
)
{
    if (drv) return STA_NOINIT;

    return Stat;
}



/*-----------------------------------------------------------------------*/
/* Initialize Disk Drive                                                 */
/*-----------------------------------------------------------------------*/

DSTATUS disk_initialize (
    BYTE drv        /* Physical drive nmuber (0) */
)
{
    BYTE n, ty, cmd, buf[4];
    UINT tmr;
    DSTATUS s;


    if (drv) return RES_NOTRDY;

    busy_wait(10);  /* 10ms */

    for (n = 10; n; n--) rcvr_mmc(buf, 1);  /* Apply 80 dummy clocks and the card gets ready to receive command */

    ty = 0;
    if (send_cmd(CMD0, 0) == 1) {           /* Enter Idle state */
        if (send_cmd(CMD8, 0x1AA) == 1) {   /* SDv2? */
            rcvr_mmc(buf, 4);                           /* Get trailing return value of R7 resp */
            if (buf[2] == 0x01 && buf[3] == 0xAA) {     /* The card can work at vdd range of 2.7-3.6V */
                for (tmr = 1000; tmr; tmr--) {          /* Wait for leaving idle state (ACMD41 with HCS bit) */
                    if (send_cmd(ACMD41, 1UL << 30) == 0) break;
                    busy_wait(1);
                }
                if (tmr && send_cmd(CMD58, 0) == 0) {   /* Check CCS bit in the OCR */
                    rcvr_mmc(buf, 4);
                    ty = (buf[0] & 0x40) ? CT_SD2 | CT_BLOCK : CT_SD2;  /* SDv2 */
                }
            }
        } else {                            /* SDv1 or MMCv3 */
            if (send_cmd(ACMD41, 0) <= 1)   {
                ty = CT_SD1; cmd = ACMD41;  /* SDv1 */
            } else {
                ty = CT_MMC; cmd = CMD1;    /* MMCv3 */
            }
            for (tmr = 1000; tmr; tmr--) {          /* Wait for leaving idle state */
                if (send_cmd(cmd, 0) == 0) break;
                busy_wait(1);
            }
            if (!tmr || send_cmd(CMD16, 512) != 0)  /* Set R/W block length to 512 */
                ty = 0;
        }
    }
    CardType = ty;
    s = ty ? 0 : STA_NOINIT;
    Stat = s;

    deselect();

    return s;
}



/*-----------------------------------------------------------------------*/
/* Read Sector(s)                                                        */
/*-----------------------------------------------------------------------*/

DRESULT disk_read (
    BYTE drv,           /* Physical drive nmuber (0) */
    BYTE *buff,         /* Pointer to the data buffer to store read data */
    LBA_t sector,       /* Start sector number (LBA) */
    UINT count          /* Sector count (1..128) */
)
{
    BYTE cmd;
    DWORD sect = (DWORD)sector;


    //FIXME if (disk_status(drv) & STA_NOINIT) return RES_NOTRDY;
    if (!(CardType & CT_BLOCK)) sect *= 512;    /* Convert LBA to byte address if needed */

    cmd = count > 1 ? CMD18 : CMD17;            /*  READ_MULTIPLE_BLOCK : READ_SINGLE_BLOCK */
    if (send_cmd(cmd, sect) == 0) {
        do {
            if (!rcvr_datablock(buff, 512)) break;
            buff += 512;
        } while (--count);
        if (cmd == CMD18) send_cmd(CMD12, 0);   /* STOP_TRANSMISSION */
    }
    deselect();

    return count ? RES_ERROR : RES_OK;
}

/*-----------------------------------------------------------------------*/
/* Write Sector(s)                                                       */
/*-----------------------------------------------------------------------*/

DRESULT disk_write (
    BYTE drv,           /* Physical drive nmuber (0) */
    const BYTE *buff,   /* Pointer to the data to be written */
    LBA_t sector,       /* Start sector number (LBA) */
    UINT count          /* Sector count (1..128) */
)
{
    DWORD sect = (DWORD)sector;


    //FIXME if (disk_status(drv) & STA_NOINIT) return RES_NOTRDY;
    if (!(CardType & CT_BLOCK)) sect *= 512;    /* Convert LBA to byte address if needed */

    if (count == 1) {   /* Single block write */
        if ((send_cmd(CMD24, sect) == 0)    /* WRITE_BLOCK */
            && xmit_datablock(buff, 0xFE))
            count = 0;
    }
    else {              /* Multiple block write */
        if (CardType & CT_SDC) send_cmd(ACMD23, count);
        if (send_cmd(CMD25, sect) == 0) {   /* WRITE_MULTIPLE_BLOCK */
            do {
                if (!xmit_datablock(buff, 0xFC)) break;
                buff += 512;
            } while (--count);
            if (!xmit_datablock(0, 0xFD))   /* STOP_TRAN token */
                count = 1;
        }
    }
    deselect();

    return count ? RES_ERROR : RES_OK;
}


/*-----------------------------------------------------------------------*/
/* Miscellaneous Functions                                               */
/*-----------------------------------------------------------------------*/

DRESULT disk_ioctl (
    BYTE drv,       /* Physical drive nmuber (0) */
    BYTE ctrl,      /* Control code */
    void *buff      /* Buffer to send/receive control data */
)
{
    DRESULT res;
    BYTE n, csd[16];
    DWORD cs;

    //FIXME if (disk_status(drv) & STA_NOINIT) return RES_NOTRDY;   /* Check if card is in the socket */

    res = RES_ERROR;
    switch (ctrl) {
        case CTRL_SYNC :        /* Make sure that no pending write process */
            if (select()) res = RES_OK;
            break;

        case GET_SECTOR_COUNT : /* Get number of sectors on the disk (DWORD) */
            if ((send_cmd(CMD9, 0) == 0) && rcvr_datablock(csd, 16)) {
                if ((csd[0] >> 6) == 1) {   /* SDC ver 2.00 */
                    cs = csd[9] + ((WORD)csd[8] << 8) + ((DWORD)(csd[7] & 63) << 16) + 1;
                    *(LBA_t*)buff = cs << 10;
                } else {                    /* SDC ver 1.XX or MMC */
                    n = (csd[5] & 15) + ((csd[10] & 128) >> 7) + ((csd[9] & 3) << 1) + 2;
                    cs = (csd[8] >> 6) + ((WORD)csd[7] << 2) + ((WORD)(csd[6] & 3) << 10) + 1;
                    *(LBA_t*)buff = cs << (n - 9);
                }
                res = RES_OK;
            }
            break;

        case GET_BLOCK_SIZE :   /* Get erase block size in unit of sector (DWORD) */
            *(DWORD*)buff = 128;
            res = RES_OK;
            break;

        default:
            res = RES_PARERR;
    }

    deselect();

    return res;
}


/*-----------------------------------------------------------------------*/
/* LiteX's BIOS                                                          */
/*-----------------------------------------------------------------------*/

uint8_t spisdcard_init(void) {
    uint8_t r;
    /* Set SPI clk freq to 400KHz */
    spi_set_clk_freq(400000);

    /* Initialize the SDCard */
    r = disk_initialize(0);

    /* Increase SPI clk freq to 16MHz if successful */
    if (r == RES_OK) {
        spi_set_clk_freq(16000000);
    }

    return (r == RES_OK);
}

uint8_t spisdcard_read_block(uint32_t addr, uint8_t *buf) {
    return (disk_read(0, buf, addr, 1) == RES_OK);
}

#endif
