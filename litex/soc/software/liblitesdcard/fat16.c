// This file is Copyright (c) 2020 Rob Shelton <rob.s.ng15@googlemail.com>
// License: BSD
//
// SD CARD code for loading files from a FAT16 formatted partition into memory

#include <generated/csr.h>
#include <generated/soc.h>
#include <generated/mem.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <string.h>
#include <system.h>

#include "spisdcard.h"
#include "sdcard.h"
#include "fat16.h"

// Return values
#define SUCCESS         0x01
#define FAILURE         0x00

#if defined(CSR_SPISDCARD_BASE) || defined(CSR_SDCORE_BASE)

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
uint8_t sdcard_readMBR(void)
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
#endif

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
uint8_t sdcard_readFile(char *filename, char *ext, unsigned long address)
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
