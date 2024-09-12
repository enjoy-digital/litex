// This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
// This file is Copyright (c) 2020 Rob Shelton <rob.s.ng15@googlemail.com>
// License: BSD

// SPI SDCard support for LiteX's SPIMaster (limited to ver2.00+ SDCards).

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <generated/csr.h>
#include <generated/mem.h>
#include <generated/soc.h>
#include <system.h>

#include <libfatfs/ff.h>
#include <libfatfs/diskio.h>
#include "spisdcard.h"

#ifdef CSR_SPISDCARD_BASE

//#define SPISDCARD_DEBUG

#ifndef SPISDCARD_CLK_FREQ_INIT
#define SPISDCARD_CLK_FREQ_INIT 400000
#endif
#ifndef SPISDCARD_CLK_FREQ
#define SPISDCARD_CLK_FREQ 20000000
#endif

/*-----------------------------------------------------------------------*/
/* SPI SDCard clocker functions                                          */
/*-----------------------------------------------------------------------*/

static void spi_set_clk_freq(uint32_t clk_freq) {
    uint32_t divider;
    divider = CONFIG_CLOCK_FREQUENCY/clk_freq + 1;
    divider = max(divider,     2);
    divider = min(divider,   256);
#ifdef SPISDCARD_DEBUG
    printf("Setting SDCard clk freq to ");
    if (clk_freq > 1000000)
        printf("%d MHz\n", (CONFIG_CLOCK_FREQUENCY/divider)/1000000);
    else
        printf("%d KHz\n", (CONFIG_CLOCK_FREQUENCY/divider)/1000);
#endif
    spisdcard_clk_divider_write(divider);
}

/*-----------------------------------------------------------------------*/
/* SPI SDCard low-level functions                                        */
/*----------------------------------------------------------------------*/

static uint8_t spi_xfer(uint8_t byte) {
    /* Write byte on MOSI */
    spisdcard_mosi_write(byte);
    /* Initiate SPI Xfer */
    spisdcard_control_write(8*SPI_LENGTH | SPI_START);
    /* Wait SPI Xfer to be done */
    while((spisdcard_status_read() & SPI_DONE) != SPI_DONE);
    /* Read MISO and return it */
    return spisdcard_miso_read();
}

/*-----------------------------------------------------------------------*/
/* SPI SDCard Select/Deselect functions                                  */
/*-----------------------------------------------------------------------*/

static void spisdcard_deselect(void) {
    /* Set SPI CS High */
    spisdcard_cs_write(SPI_CS_HIGH);
    /* Generate 8 dummy clocks */
    spi_xfer(0xff);
}

static int spisdcard_select(void) {
    uint16_t timeout;

    /* Set SPI CS Low */
    spisdcard_cs_write(SPI_CS_LOW);

    /* Generate 8 dummy clocks */
    spi_xfer(0xff);

    /* Wait 500ms for the card to be ready */
    timeout = 500;
    while(timeout > 0) {
        if (spi_xfer(0xff) == 0xff)
            return 1;
        busy_wait(1);
        timeout--;
    }

    /* Deselect card on error */
    spisdcard_deselect();

    return 0;
}

/*-----------------------------------------------------------------------*/
/* SPI SDCard bytes Xfer functions                                       */
/*-----------------------------------------------------------------------*/

static void spisdcardwrite_bytes(uint8_t* buf, uint16_t n) {
    uint16_t i;
    for (i=0; i<n; i++)
        spi_xfer(buf[i]);
}

static void spisdcardread_bytes(uint8_t* buf, uint16_t n) {
    uint16_t i;
    for (i=0; i<n; i++)
        buf[i] = spi_xfer(0xff);
}

/*-----------------------------------------------------------------------*/
/* SPI SDCard blocks Xfer functions                                      */
/*-----------------------------------------------------------------------*/

static uint8_t spisdcardreceive_block(uint8_t *buf) {
    uint16_t i;
    uint32_t timeout;

    /* Wait 100ms for a start of block */
    timeout = 100000;
    while(timeout > 0) {
        if (spi_xfer(0xff) == 0xfe)
            break;
        busy_wait_us(1);
        timeout--;
    }
    if (timeout == 0)
        return 0;

    /* Receive block */
    spisdcard_mosi_write(0xff);
    for (i=0; i<512; i++) {
        spisdcard_control_write(8*SPI_LENGTH | SPI_START);
        while (spisdcard_status_read() != SPI_DONE);
        *buf++ = spisdcard_miso_read();
    }

    /* Discard CRC */
    spi_xfer(0xff);
    spi_xfer(0xff);

    return 1;
}

/*-----------------------------------------------------------------------*/
/* SPI SDCard Command functions                                          */
/*-----------------------------------------------------------------------*/

static uint8_t spisdcardsend_cmd(uint8_t cmd, uint32_t arg)
{
    uint8_t byte;
    uint8_t buf[6];
    uint8_t timeout;

    /* Send CMD55 for ACMD */
    if (cmd & 0x80) {
        cmd &= 0x7f;
        byte = spisdcardsend_cmd(CMD55, 0);
        if (byte > 1)
            return byte;
    }

    /* Select the card and wait for it, except for:
       - CMD12: STOP_TRANSMISSION.
       - CMD0 : GO_IDLE_STATE.
    */
    if (cmd != CMD12 && cmd != CMD0) {
        spisdcard_deselect();
        if (spisdcard_select() == 0)
            return 0xff;
    }

    /* Send Command */
    buf[0] = 0x40 | cmd;            /* Start + Command */
    buf[1] = (uint8_t)(arg >> 24);  /* Argument[31:24] */
    buf[2] = (uint8_t)(arg >> 16);  /* Argument[23:16] */
    buf[3] = (uint8_t)(arg >> 8);   /* Argument[15:8] */
    buf[4] = (uint8_t)(arg >> 0);   /* Argument[7:0] */
    if (cmd == CMD0)
        buf[5] = 0x95;      /* Valid CRC for CMD0 */
    else if (cmd == CMD8)
        buf[5] = 0x87;      /* Valid CRC for CMD8 (0x1AA) */
    else
        buf[5] = 0x01;      /* Dummy CRC + Stop */
    spisdcardwrite_bytes(buf, 6);

    /* Receive Command response */
    if (cmd == CMD12)
        spisdcardread_bytes(&byte, 1);  /* Read stuff byte */
    timeout = 10; /* Wait for a valid response (up to 10 attempts) */
    while (timeout > 0) {
        spisdcardread_bytes(&byte, 1);
        if ((byte & 0x80) == 0)
            break;

        timeout--;
    }
    return byte;
}

/*-----------------------------------------------------------------------*/
/* SPI SDCard Initialization functions                                   */
/*-----------------------------------------------------------------------*/

uint8_t spisdcard_init(void) {
    uint8_t  i;
    uint8_t  buf[4];
    uint16_t timeout;

    /* Set SPI clk freq to initialization frequency */
    spi_set_clk_freq(SPISDCARD_CLK_FREQ_INIT);

    timeout = 1000;
    while (timeout) {
        /* Set SDCard in SPI Mode (generate 80 dummy clocks) */
        spisdcard_cs_write(SPI_CS_HIGH);
        for (i=0; i<10; i++)
            spi_xfer(0xff);
        spisdcard_cs_write(SPI_CS_LOW);

        /* Set SDCard in Idle state */
        if (spisdcardsend_cmd(CMD0, 0) == 0x1)
            break;

        timeout--;
    }
    if (timeout == 0)
        return 0;

    /* Set SDCard voltages, only supported by ver2.00+ SDCards */
    if (spisdcardsend_cmd(CMD8, 0x1AA) != 0x1)
        return 0;
    spisdcardread_bytes(buf, 4); /* Get additional bytes of R7 response */

    /* Set SDCard in Operational state (1s timeout) */
    timeout = 1000;
    while (timeout > 0) {
        if (spisdcardsend_cmd(ACMD41, 1 << 30) == 0)
            break;
        busy_wait(1);
        timeout--;
    }
    if (timeout == 0)
        return 0;

    /* Set SPI clk freq to operational frequency */
    spi_set_clk_freq(SPISDCARD_CLK_FREQ);

    return 1;
}

/*-----------------------------------------------------------------------*/
/* SPI SDCard FatFs functions                                            */
/*-----------------------------------------------------------------------*/

static DSTATUS spisdcardstatus = STA_NOINIT;

static DSTATUS spisd_disk_status(BYTE drv) {
    if (drv) return STA_NOINIT;
    return spisdcardstatus;
}

static DSTATUS spisd_disk_initialize(BYTE drv) {
    if (drv) return STA_NOINIT;
    if (spisdcardstatus) {
        spisdcardstatus = spisdcard_init() ? 0 : STA_NOINIT;
        spisdcard_deselect();
    }
    return spisdcardstatus;
}

static DRESULT spisd_disk_read(BYTE drv, BYTE *buf, LBA_t block, UINT count) {
    uint8_t cmd;
    if (count > 1)
        cmd = CMD18; /* READ_MULTIPLE_BLOCK */
    else
        cmd = CMD17; /* READ_SINGLE_BLOCK */
    if (spisdcardsend_cmd(cmd, block) == 0) {
        while(count > 0) {
            if (spisdcardreceive_block(buf) == 0)
                break;
            buf += 512;
            count--;
        }
        if (cmd == CMD18)
            spisdcardsend_cmd(CMD12, 0); /* STOP_TRANSMISSION */
    }
    spisdcard_deselect();

    if (count)
        return RES_ERROR;

    return RES_OK;
}

static DISKOPS SpiSdDiskOps = {
	.disk_initialize = spisd_disk_initialize,
	.disk_status = spisd_disk_status,
	.disk_read = spisd_disk_read,
};

void fatfs_set_ops_spisdcard(void) {
	FfDiskOps = &SpiSdDiskOps;
}

#endif
