// This file is Copyright (c) 2020 Rob Shelton <rob.s.ng15@googlemail.com>
// License: BSD
//
// SD CARD bitbanging code for loading files from a FAT16 forrmatted partition into memory
//
// Code is known to work on a de10nano with MiSTer SDRAM and IO Boards - IO Board has a secondary SD CARD interface connected to GPIO pins
// SPI signals CLK, CS and MOSI are configured as GPIO output pins, and MISO is configued as GPIO input pins
//
// Protocol details developed from https://openlabpro.com/guide/interfacing-microcontrollers-with-sd-card/
//
// FAT16 details developed from https://codeandlife.com/2012/04/02/simple-fat-and-sd-tutorial-part-1/ and https://codeandlife.com/2012/04/07/simple-fat-and-sd-tutorial-part-2/

// Import LiteX SoC details that are generated each time the SoC is compiled for the FPGA
//      csr defines the SPI Control registers
//      soc defines the clock CONFIG_CLOCK_FREQUENCY (50MHz for the VexRiscV processor on the MiSTer FPGA
//      mem defines the addresses for the SDRAM MAIN_RAM_BASE and MAIN_RAM_SIZE
#include <generated/csr.h>
#include <generated/soc.h>
#include <generated/mem.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <string.h>
#include <system.h>

#ifdef CSR_SPISDCARD_BASE
// Import prototypes for the functions
#include "spisdcard.h"

// SPI
//      cs line - high to indicate DESELECT
//              - low to indicate SELECT
#define CS_HIGH         0x00
#define CS_LOW          0x01

//      control register values
//      onebyte to indicate 1 byte being transferred
//      spi_start to indicate START of transfer
//      spi_done to indicate transfer DONE
#define ONEBYTE         0x0800
#define SPI_START       0x01
#define SPI_DONE        0x01

// Return values
#define SUCCESS         0x01
#define FAILURE         0x00

// spi_write_byte
//      Send a BYTE (8bits) to the SD CARD
//      Seqeunce
//          Set MOSI
//          Set START bit and LENGTH=8
//          Await DONE
//
//      No return values
//
//      Details from https://openlabpro.com/guide/interfacing-microcontrollers-with-sd-card/ section "SD Commands"
void spi_write_byte(uint8_t char_to_send);
void spi_write_byte(uint8_t char_to_send)
{
    // Place data into MOSI register
    // Pulse the START bit and set LENGTH=8
    spisdcard_mosi_write(char_to_send);
    spisdcard_control_write(ONEBYTE | SPI_START);

    // Wait for DONE
    while( (spisdcard_status_read() != SPI_DONE)) {}

    // Signal end of transfer
    spisdcard_control_write( 0x00 );
}


// spi_read_rbyte
//      Read a command response from the SD CARD - Equivalent to and R1 response or first byte of an R7 response
//      Sequence
//          Read MISO
//          If MSB != 0 then send dsummy byte and re-read MISO
//
//      Return value is the response from the SD CARD
//          If the MSB is not 0, this would represent an ERROR
//          Calling function to determine if the correct response has been received
//
//      Details from https://openlabpro.com/guide/interfacing-microcontrollers-with-sd-card/ section "SD Commands"
uint8_t spi_read_rbyte(void);
uint8_t spi_read_rbyte(void)
{
    int timeout=32;
    uint8_t r=0;

    // Check if MISO is 0x0xxxxxxx as MSB=0 indicates valid response
    r = spisdcard_miso_read();
    while( ((r&0x80)!=0) && timeout>0) {
        spisdcard_mosi_write( 0xff );
        spisdcard_control_write(ONEBYTE | SPI_START);
        while( (spisdcard_status_read() != SPI_DONE)) {}
        r = spisdcard_miso_read();
        spisdcard_control_write( 0x00 );
        timeout--;
    }

//    printf("Done\n");
    return r;
}

// spi_read_byte
//      Sequence
//          Send dummy byte
//          Read MISO
//
//      Read subsequenct bytes from the SD CARD - MSB first
//      NOTE different from the spi_read_rbyte as no need to await an intial 0 bit as card is already responsing
//      Used to read additional response bytes, or data bytes from the SD CARD
//
//      Return value is the byte read
//          NOTE no error status as assumed bytes are read via CLK pulses
//
//      Details from https://openlabpro.com/guide/interfacing-microcontrollers-with-sd-card/ section "SD Commands"
uint8_t spi_read_byte(void);
uint8_t spi_read_byte(void)
{
    uint8_t r=0;

    spi_write_byte( 0xff );
    r = spisdcard_miso_read();

    return r;
}

//  SETSPIMODE
//      Signal the SD CARD to switch to SPI mode
//      Pulse the CLK line HIGH/LOW repeatedly with MOSI and CS_N HIGH
//      Drop CS_N LOW and pulse the CLK
//      Check MISO for HIGH
//      Return 0 success, 1 failure
//
//      Details from https://openlabpro.com/guide/interfacing-microcontrollers-with-sd-card/ section "Initializing the SD Card"
uint8_t spi_setspimode(void);
uint8_t spi_setspimode(void)
{
    uint32_t r;
    int i, timeout=32;

    // Initialise SPI mode
    // set CS to HIGH
    // Send pulses
     do {
        // set CS HIGH and send pulses
        spisdcard_cs_write(CS_HIGH);
         for (i=0; i<10; i++) {
            spi_write_byte( 0xff );
        }

        // set CS LOW and send pulses
        spisdcard_cs_write(CS_LOW);
        r = spi_read_rbyte();

        timeout--;
    } while ( (timeout>0) && (r==0) );

    if(timeout==0) return FAILURE;

    return SUCCESS;
}

// SPI_SDCARD_GOIDLE
//      Function exposed to BIOS to initialise SPI mode
//
//      Sequence
//          Set 100KHz timer mode
//          Send CLK pulses to set SD CARD to SPI mode
//          Send CMD0 - Software RESET - force SD CARD IDLE
//          Send CMD8 - Check SD CARD type
//          Send CMD55+ACMD41 - Force SD CARD READY
//          Send CMD58 - Read SD CARD OCR (status register)
//          Send CMD16 - Set SD CARD block size to 512 - Sector Size for the SD CARD
//      NOTE - Each command is prefixed with a dummy set of CLK pulses to prepare SD CARD to receive a command
//      Return 0 success, 1 failure
//
//      Details from https://openlabpro.com/guide/interfacing-microcontrollers-with-sd-card/ section "Initializing the SD Card"
uint8_t spi_sdcard_goidle(void)
{
    uint8_t r;                                                                                                                // Response from SD CARD
    int i, timeout;                                                                                                                 // TIMEOUT loop to send CMD55+ACMD41 repeatedly

    r = spi_setspimode();                                                                                                               // Set SD CARD to SPI mode
    if( r != 0x01 ) return FAILURE;

    // CMD0 - Software reset - SD CARD IDLE
    // Command Sequence is DUMMY=0xff CMD0=0x40 0x00 0x00 0x00 0x00 CRC=0x95
    // Expected R1 response is 0x01 indicating SD CARD is IDLE
    spi_write_byte( 0xff ); spi_write_byte( 0x40 ); spi_write_byte( 0x00 ); spi_write_byte( 0x00 ); spi_write_byte( 0x00 ); spi_write_byte( 0x00 ); spi_write_byte( 0x95 );
    r = spi_read_rbyte();
    if(r!=0x01) return FAILURE;

    // CMD8 - Check SD CARD type
    // Command sequence is DUMMY=0xff CMD8=0x48 0x00 0x00 0x01 0xaa CRC=0x87
    // Expected R7 response is 0x01 followed by 0x00 0x00 0x01 0xaa (these trailing 4 bytes not currently checked)
    spi_write_byte( 0xff ); spi_write_byte( 0x48 ); spi_write_byte( 0x00 ); spi_write_byte( 0x00 ); spi_write_byte( 0x01 ); spi_write_byte( 0xaa ); spi_write_byte( 0x87 );
    r = spi_read_rbyte();
    if(r!=0x01) return FAILURE;
    // Receive the trailing 4 bytes for R7 response - FIXME should check for 0x00 0x00 0x01 0xaa
    for(i=0; i<4; i++)
        r=spi_read_byte();

    // CMD55+ACMD41 - Force SD CARD READY - prepare card for reading/writing
    // Command sequence is CMD55 followed by ACMD41
    //      Send commands repeatedly until SD CARD indicates READY 0x00
    // CMD55 Sequence is DUMMY=0xff CMD55=0x77 0x00 0x00 0x00 0x00 CRC=0x00
    // ACMD41 Sequence is DUMMY=0xff ACMD41=0x69 0x40 0x00 0x00 0x00 CRC=0x00
    // Expected R1 response is 0x00 indicating SD CARD is READY
    timeout=32;
    do {
        spi_write_byte( 0xff ); spi_write_byte( 0x77 ); spi_write_byte( 0x00 ); spi_write_byte( 0x00 ); spi_write_byte( 0x00 ); spi_write_byte( 0x00 ); spi_write_byte( 0x00 );
        r = spi_read_rbyte();

        spi_write_byte( 0xff ); spi_write_byte( 0x69 ); spi_write_byte( 0x40 ); spi_write_byte( 0x00 ); spi_write_byte( 0x00 ); spi_write_byte( 0x00 ); spi_write_byte( 0x00 );
        r = spi_read_rbyte();
        timeout--;
        busy_wait(20);
    } while ((r != 0x00) && (timeout>0));
    if(r!=0x00) return FAILURE;

    // CMD58 - Read SD CARD OCR (status register)
    // FIXME - Find details on expected response from CMD58 to allow accurate checking of SD CARD R3 response
    // Command sequence is DUMMY=0xff CMD58=0x7a 0x00 0x00 0x01 0xaa CRC=0xff
    // Expected R3 response is 0x00 OR 0x01 followed by 4 (unchecked) trailing bytes
    spi_write_byte( 0xff ); spi_write_byte( 0x7a ); spi_write_byte( 0x00 ); spi_write_byte( 0x00 ); spi_write_byte( 0x00 ); spi_write_byte( 0x00 ); spi_write_byte( 0xff );
    r = spi_read_rbyte();
    if(r>0x01) return FAILURE;
    // // Receive the trailing 4 bytes for R3 response
    for(i=0; i<4; i++)
        r=spi_read_byte();

    // CMD16 - Set SD CARD block size to 512 - Sector Size for the SD CARD
    // Command Sequence is DUMMY=0xff CMD16=0x50 (512 as unsigned 32bit = 0x00000200) 0x00 0x00 0x02 0x00 CRC=0xff
    // Expected R1 response is 0x00 indicating SD CARD is READY
    spi_write_byte( 0xff ); spi_write_byte( 0x50 ); spi_write_byte( 0x00 ); spi_write_byte( 0x00 ); spi_write_byte( 0x02 ); spi_write_byte( 0x00 ); spi_write_byte( 0xff );
    r=spi_read_rbyte();
    if(r!=0x00) return FAILURE;

    return SUCCESS;
}

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
    int n, timeout;                                                                                                             // Number of bytes loop, timeout loop awaiting response bytes
    uint8_t r;                                                                                                                    // Response bytes from SD CARD

    // CMD17 - Read Block
    // Command Sequence is DUMMY=0xff CMD17=0x51 SECTORNUMBER (32bit UNSIGNED as bits 32-25,24-17, 16-9, 8-1) CRC=0xff
    // Expected R1 response is 0x00 indicating SD CARD is processing
    spi_write_byte( 0xff ); spi_write_byte( 0x51 ); spi_write_byte( (sectorNumber>>24)&0xff ); spi_write_byte( (sectorNumber>>16)&0xff ); spi_write_byte( (sectorNumber>>8)&0xff ); spi_write_byte( (sectorNumber)&0xff ); spi_write_byte( 0xff );
    r=spi_read_rbyte();
    if( r!=0x00 ) return FAILURE;

    // Await 0xfe to indicate BLOCK START
    r=spi_read_byte();
    timeout=16384;
    while( (r!=0xfe) && (timeout>0) ) {
        r=spi_read_byte();
        timeout--;
    }
    if( r!=0xfe ) return FAILURE;

    // Read 512 bytes into storage
    for(n=0; n<512; n++)
        storage[n]=spi_read_byte();

    // Read 8 dummy bytes
    for(n=0; n<8; n++)
        r=spi_read_byte();

    return SUCCESS;
}

#endif
