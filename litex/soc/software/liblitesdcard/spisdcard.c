// This file is Copyright (c) 2020 Rob Shelton <rob.s.ng15@googlemail.com>
// This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD
//
// SDCard SPI-Mode support for LiteX's SPIMaster.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <generated/csr.h>
#include <generated/mem.h>
#include <system.h>

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

/* SPI SDCard functions */

static uint8_t spisdcard_wait_response(void) {
    uint8_t timeout;
    uint8_t response;

    timeout  = 32;
    /* Do SPI Xfers on SDCard until MISO MSB's is 0 (valid response) or timeout is expired */
    do {
        response = spi_xfer(0xff);
        timeout--;
    } while(((response & 0x80) !=0) && timeout > 0);
    return response;
}

static uint8_t spisdcard_set_mode(void) {
    uint8_t timeout;
    uint8_t response;

    timeout = 32;
    do {
        int i;
        /* Set CS and send 80 clock pulses to set the SDCard in SPI Mode */
        spisdcard_cs_write(SPI_CS_HIGH);
        for (i=0; i<10; i++)
            spi_xfer(0xff);
        /* Clear CS and read response, if 0 the SDCard has been initialized to SPI Mode */
        spisdcard_cs_write(SPI_CS_LOW);
        response = spisdcard_wait_response();

        timeout--;
    } while ((timeout > 0) && (response == 0));

    if(timeout == 0)
        return 0;

    return 1;
}

uint8_t spisdcard_init(void) {
    uint8_t i;
    uint8_t r;
    uint8_t timeout;

    /* Set SPI clk freq to 400KHz */
    spi_set_clk_freq(400000);

    /* Set SDCard in SPI Mode */
    r = spisdcard_set_mode();
    if(r != 0x01)
        return 0;

    /* Send SD CARD IDLE */
    /* CMD0 */
    spi_xfer(0xff);
    spi_xfer(0x40);
    spi_xfer(0x00);
    spi_xfer(0x00);
    spi_xfer(0x00);
    spi_xfer(0x00);
    spi_xfer(0x95);
    /* R1 response, expects 0x1 */
    r = spisdcard_wait_response();
    if(r != 0x01)
        return 0;

    /* Send Check SD CARD type */
    /* CMD8 */
    spi_xfer(0xff);
    spi_xfer(0x48);
    spi_xfer(0x00);
    spi_xfer(0x00);
    spi_xfer(0x01);
    spi_xfer(0xaa);
    spi_xfer(0x87);
    /* R7, expects 0x1 */
    r = spisdcard_wait_response();
    if(r != 0x01)
        return 0;
    /* Reveice the 4 trailing bytes */
    for(i=0; i<4; i++)
        r = spi_xfer(0xff); /* FIXME: add check? */

    /* Send Force SD CARD READY (CMD55 + ACMD41), expects 0x00 R1 response */
    timeout = 32;
    do {
        /* CMD55 */
        spi_xfer(0xff);
        spi_xfer(0x77);
        spi_xfer(0x00);
        spi_xfer(0x00);
        spi_xfer(0x00);
        spi_xfer(0x00);
        spi_xfer(0x00);
        r = spisdcard_wait_response();
        /* ACMD41 */
        spi_xfer(0xff);
        spi_xfer(0x69);
        spi_xfer(0x40);
        spi_xfer(0x00);
        spi_xfer(0x00);
        spi_xfer(0x00);
        spi_xfer(0x00);
        /* R1 */
        r = spisdcard_wait_response();
        timeout--;
        /* 20ms delay */
        busy_wait(20);
    } while ((r != 0x00) && (timeout > 0));
    if(r != 0x00)
        return 0;

    /* Send Read SD CARD OCR (status register) */
    /* CMD58 */
    spi_xfer(0xff);
    spi_xfer(0x7a);
    spi_xfer(0x00);
    spi_xfer(0x00);
    spi_xfer(0x00);
    spi_xfer(0x00);
    spi_xfer(0xff);
    /* R3, expects 0x1 */
    r = spisdcard_wait_response();
    if(r > 0x01)
        return 0;
    /* Reveice the 4 trailing bytes */
    for(i=0; i<4; i++)
        r = spi_xfer(0xff); /* FIXME: add check? */

    /* Send Set SD CARD block size */
    /* CMD16 */
    spi_xfer(0xff);
    spi_xfer(0x50);
    spi_xfer(0x00);
    spi_xfer(0x00);
    spi_xfer(0x02);
    spi_xfer(0x00);
    spi_xfer(0xff);
    /* RI, expects 0x00 */
    r = spisdcard_wait_response();
    if(r != 0x00)
        return 0;

    /* Set SPI clk freq to 16MHz */
    spi_set_clk_freq(16000000);

    return 1;
}

uint8_t spisdcard_read_block(uint32_t addr, uint8_t *buf) {
    int i;
    uint32_t timeout;
    uint8_t r;

    /* Send Read Block */
    /* CMD17 */
    spi_xfer(0xff);
    spi_xfer(0x51);
    spi_xfer((addr >> 24) & 0xff);
    spi_xfer((addr >> 16) & 0xff);
    spi_xfer((addr >>  8) & 0xff);
    spi_xfer((addr >>  0) & 0xff);
    spi_xfer(0xff);
    /* R1, expects 0x00 that indicates the SDCard is processing */
    r = spisdcard_wait_response();
    if(r != 0x00)
        return 0;

    /* Do SPI Xfers on SDCard until 0xfe is received (block start) or timeout is expired */
    r = spi_xfer(0xff);
    timeout = 16384;
    do {
        r = spi_xfer(0xff);
        timeout--;
    } while((r != 0xfe) && (timeout>0));
    if(r != 0xfe)
        return 0;

    /* Read the block from the SDCard and copy it to the buffer */
    for(i=0; i<512; i++)
        buf[i] = spi_xfer(0xff);

    /* Read the 8 dummy bytes */
    for(i=0; i<8; i++)
        r = spi_xfer(0xff);

    return 1;
}

#endif
