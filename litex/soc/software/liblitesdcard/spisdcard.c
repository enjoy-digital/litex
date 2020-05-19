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

#define USE_SPISCARD_RECLOCKING

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

#ifdef USE_SPISCARD_RECLOCKING
    // Reclock the card
    // Calculate 16MHz as an integer divider from the CONFIG_CLOCK_FREQUENCY
    // Add 1 as will be rounded down
    // Always ensure divider is at least 2 - half the processor speed
    int divider;
    divider = (int)(CONFIG_CLOCK_FREQUENCY/(16e6)) + 1;
    if( divider<2 )
        divider=2;
    printf("Reclocking from %dKHz to %dKHz\n\n", CONFIG_CLOCK_FREQUENCY/(int)spisdcard_clk_divider_read()/1000, CONFIG_CLOCK_FREQUENCY/divider/1000);
    spisdcard_clk_divider_write(divider);

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
#endif

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
#endif
