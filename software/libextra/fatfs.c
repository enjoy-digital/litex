/*
 * Milkymist SoC (Software)
 * Copyright (C) 2007, 2008, 2009, 2010 Sebastien Bourdeauducq
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <ctype.h>
#include <endian.h>
#include <console.h>
#include <blockdev.h>

#include <fatfs.h>

//#define DEBUG

#define BLOCK_SIZE 512

struct partition_descriptor {
	unsigned char flags;
	unsigned char start_head;
	unsigned short start_cylinder;
	unsigned char type;
	unsigned char end_head;
	unsigned short end_cylinder;
	unsigned int start_sector;
	unsigned int end_sector;
} __attribute__((packed));

struct firstsector {
	unsigned char bootsector[446];
	struct partition_descriptor partitions[4];
	unsigned char signature[2];
} __attribute__((packed));


struct fat16_firstsector {
	/* Common to FATxx */
	char jmp[3];
	char oem[8];
	unsigned short bytes_per_sector;
	unsigned char sectors_per_cluster;
	unsigned short reserved_sectors;
	unsigned char number_of_fat;
	unsigned short max_root_entries;
	unsigned short total_sectors_short;
	unsigned char media_descriptor;
	unsigned short sectors_per_fat;
	unsigned short sectors_per_track;
	unsigned short head_count;
	unsigned int hidden_sectors;
	unsigned int total_sectors;
	
	/* FAT16 specific */
	unsigned char drive_nr;
	unsigned char reserved;
	unsigned char ext_boot_signature;
	unsigned int id;
	unsigned char volume_label[11];
	unsigned char fstype[8];
	unsigned char bootcode[448];
	unsigned char signature[2];
} __attribute__((packed));

struct directory_entry {
	unsigned char filename[8];
	unsigned char extension[3];
	unsigned char attributes;
	unsigned char reserved;
	unsigned char create_time_ms;
	unsigned short create_time;
	unsigned short create_date;
	unsigned short last_access;
	unsigned short ea_index;
	unsigned short lastm_time;
	unsigned short lastm_date;
	unsigned short first_cluster;
	unsigned int file_size;
} __attribute__((packed));

struct directory_entry_lfn {
	unsigned char seq;
	unsigned short name1[5]; /* UTF16 */
	unsigned char attributes;
	unsigned char reserved;
	unsigned char checksum;
	unsigned short name2[6];
	unsigned short first_cluster;
	unsigned short name3[2];
} __attribute__((packed));

#define PARTITION_TYPE_FAT16		0x06
#define PARTITION_TYPE_FAT32		0x0b

static int fatfs_partition_start_sector;	/* Sector# of the beginning of the FAT16 partition */

static int fatfs_sectors_per_cluster;
static int fatfs_fat_sector;			/* Sector of the first FAT */
static int fatfs_fat_entries;			/* Number of entries in the FAT */
static int fatfs_max_root_entries;
static int fatfs_root_table_sector;		/* Sector# of the beginning of the root table */

static int fatfs_fat_cached_sector;
static unsigned short int fatfs_fat_sector_cache[BLOCK_SIZE/2];

static int fatfs_dir_cached_sector;
static struct directory_entry fatfs_dir_sector_cache[BLOCK_SIZE/sizeof(struct directory_entry)];

static int fatfs_data_start_sector;

int fatfs_init(int devnr)
{
	struct firstsector s0;
	struct fat16_firstsector s;
	int i;

	if(!bd_init(devnr)) {
		printf("E: Unable to initialize memory card driver\n");
		return 0;
	}

	if(bd_has_part_table(devnr)) {
		/* Read sector 0, with partition table */
		if(!bd_readblock(0, (void *)&s0)) {
			printf("E: Unable to read block 0\n");
			return 0;
		}

		fatfs_partition_start_sector = -1;
		for(i=0;i<4;i++)
			if((s0.partitions[i].type == PARTITION_TYPE_FAT16)
			||(s0.partitions[i].type == PARTITION_TYPE_FAT32)) {
#ifdef DEBUG
				printf("I: Using partition #%d: start sector %08x, end sector %08x\n", i,
					le32toh(s0.partitions[i].start_sector), le32toh(s0.partitions[i].end_sector));
#endif
				fatfs_partition_start_sector = le32toh(s0.partitions[i].start_sector);
				break;
			}
		if(fatfs_partition_start_sector == -1) {
			printf("E: No FAT partition was found\n");
			return 0;
		}
	} else
		fatfs_partition_start_sector = 0;
	
	/* Read first FAT16 sector */
	if(!bd_readblock(fatfs_partition_start_sector, (void *)&s)) {
		printf("E: Unable to read first FAT sector\n");
		return 0;
	}
	
#ifdef DEBUG
	{
		char oem[9];
		char volume_label[12];
		memcpy(oem, s.oem, 8);
		oem[8] = 0;
		memcpy(volume_label, s.volume_label, 11);
		volume_label[11] = 0;
		printf("I: OEM name: %s\n", oem);
		printf("I: Volume label: %s\n", volume_label);
	}
#endif
	
	if(le16toh(s.bytes_per_sector) != BLOCK_SIZE) {
		printf("E: Unexpected number of bytes per sector (%d)\n", le16toh(s.bytes_per_sector));
		return 0;
	}
	fatfs_sectors_per_cluster = s.sectors_per_cluster;
	
	fatfs_fat_entries = (le16toh(s.sectors_per_fat)*BLOCK_SIZE)/2;
	fatfs_fat_sector = fatfs_partition_start_sector + 1;
	fatfs_fat_cached_sector = -1;
	
	fatfs_max_root_entries = le16toh(s.max_root_entries);
	fatfs_root_table_sector = fatfs_fat_sector + s.number_of_fat*le16toh(s.sectors_per_fat);
	fatfs_dir_cached_sector = -1;
	
	fatfs_data_start_sector = fatfs_root_table_sector + (fatfs_max_root_entries*sizeof(struct directory_entry))/BLOCK_SIZE;

	if(fatfs_max_root_entries == 0) {
		printf("E: Your memory card uses FAT32, which is not supported.\n");
		printf("E: Please reformat your card using FAT16, e.g. use mkdosfs -F 16\n");
		printf("E: FAT32 support would be an appreciated contribution.\n");
		return 0;
	}
	
#ifdef DEBUG
	printf("I: Cluster is %d sectors, FAT has %d entries, FAT 1 is at sector %d,\nI: root table is at sector %d (max %d), data is at sector %d, nb of fat: %d\n",
		fatfs_sectors_per_cluster, fatfs_fat_entries, fatfs_fat_sector,
		fatfs_root_table_sector, fatfs_max_root_entries,
		fatfs_data_start_sector, s.number_of_fat);
#endif
	return 1;
}

static int fatfs_read_fat(int offset)
{
	int wanted_sector;
	
	if((offset < 0) || (offset >= fatfs_fat_entries)) {
		printf("E: Incorrect offset %d in fatfs_read_fat\n", offset);
		return -1;
	}
		
	wanted_sector = fatfs_fat_sector + (offset*2)/BLOCK_SIZE;
	if(wanted_sector != fatfs_fat_cached_sector) {
		if(!bd_readblock(wanted_sector, (void *)&fatfs_fat_sector_cache)) {
			printf("E: Memory card failed (FAT), sector %d\n", wanted_sector);
			return -1;
		}
		fatfs_fat_cached_sector = wanted_sector;
	}
	
	return le16toh(fatfs_fat_sector_cache[offset % (BLOCK_SIZE/2)]);
}

static const struct directory_entry *fatfs_read_root_directory(int offset)
{
	int wanted_sector;
	
	if((offset < 0) || (offset >= fatfs_max_root_entries))
		return NULL;

	wanted_sector = fatfs_root_table_sector + (offset*sizeof(struct directory_entry))/BLOCK_SIZE;

	if(wanted_sector != fatfs_dir_cached_sector) {
		if(!bd_readblock(wanted_sector, (void *)&fatfs_dir_sector_cache)) {
			printf("E: Memory card failed (Rootdir), sector %d\n", wanted_sector);
			return NULL;
		}
		fatfs_dir_cached_sector = wanted_sector;
	}
	return &fatfs_dir_sector_cache[offset % (BLOCK_SIZE/sizeof(struct directory_entry))];
}

static void lfn_to_ascii(const struct directory_entry_lfn *entry, char *name, int terminate)
{
	int i;
	unsigned short c;

	for(i=0;i<5;i++) {
		c = le16toh(entry->name1[i]);
		if(c <= 255) {
			*name = c;
			name++;
			if(c == 0) return;
		}
	}
	for(i=0;i<6;i++) {
		c = le16toh(entry->name2[i]);
		if(c <= 255) {
			*name = c;
			name++;
			if(c == 0) return;
		}
	}
	for(i=0;i<2;i++) {
		c = le16toh(entry->name3[i]);
		if(c <= 255) {
			*name = c;
			name++;
			if(c == 0) return;
		}
	}

	if(terminate)
		*name = 0;
}

static int fatfs_is_regular(const struct directory_entry *entry)
{
	return ((entry->attributes & 0x10) == 0)
		&& ((entry->attributes & 0x08) == 0)
		&& (entry->filename[0] != 0xe5);
}

int fatfs_list_files(fatfs_dir_callback cb, void *param)
{
	const struct directory_entry *entry;
	char fmtbuf[8+1+3+1];
	char longname[131];
	int has_longname;
	int i, j, k;

	has_longname = 0;
	longname[sizeof(longname)-1] = 0; /* avoid crashing when reading a corrupt FS */
	for(k=0;k<fatfs_max_root_entries;k++) {
		entry = fatfs_read_root_directory(k);
#ifdef DEBUG
		printf("I: Read entry with attribute %02x\n", entry->attributes);
#endif
		if(entry->attributes == 0x0f) {
			const struct directory_entry_lfn *entry_lfn;
			unsigned char frag;
			int terminate;

			entry_lfn = (const struct directory_entry_lfn *)entry;
			frag = entry_lfn->seq & 0x3f;
			terminate = entry_lfn->seq & 0x40;
			if(frag*13 < sizeof(longname)) {
				lfn_to_ascii((const struct directory_entry_lfn *)entry, &longname[(frag-1)*13], terminate);
				if(frag == 1) has_longname = 1;
			}
			continue;
		} else {
			if(!fatfs_is_regular(entry)) {
				has_longname = 0;
				continue;
			}
		}
		if(entry == NULL) return 0;
		if(entry->filename[0] == 0) {
			has_longname = 0;
			break;
		}
		j = 0;
		for(i=0;i<8;i++) {
			if(entry->filename[i] == ' ') break;
			fmtbuf[j++] = entry->filename[i];
		}
		fmtbuf[j++] = '.';
		for(i=0;i<3;i++) {
			if(entry->extension[i] == ' ') break;
			fmtbuf[j++] = entry->extension[i];
		}
		fmtbuf[j++] = 0;
		if(!cb(fmtbuf, has_longname ? longname : fmtbuf, param)) return 0;
		has_longname = 0;
	}
	return 1;
}

static const struct directory_entry *fatfs_find_file_by_name(const char *filename)
{
	char searched_filename[8];
	char searched_extension[3];
	char *dot;
	const char *c;
	int i;
	const struct directory_entry *entry;
	
	dot = strrchr(filename, '.');
	if(dot == NULL)
		return NULL;
	
	memset(searched_filename, ' ', 8);
	memset(searched_extension, ' ', 3);
	i = 0;
	for(c=filename;c<dot;c++)
		searched_filename[i++] = toupper(*c);
		
	i = 0;
	for(c=dot+1;*c!=0;c++)
		searched_extension[i++] = toupper(*c);
		
	for(i=0;i<fatfs_max_root_entries;i++) {
		entry = fatfs_read_root_directory(i);
		if(entry == NULL) break;
		if(entry->filename[0] == 0) break;
		if(!fatfs_is_regular(entry)) continue;
		if(!memcmp(searched_filename, entry->filename, 8)
		 &&!memcmp(searched_extension, entry->extension, 3))
		 	return entry;
	}
	return NULL;
}

static int fatfs_load_cluster(int clustern, char *buffer, int maxsectors)
{
	int startsector;
	int i;
	int toread;
	
	clustern = clustern - 2;
	startsector = fatfs_data_start_sector + clustern*fatfs_sectors_per_cluster;
	if(maxsectors < fatfs_sectors_per_cluster)
		toread = maxsectors;
	else
		toread = fatfs_sectors_per_cluster;
	for(i=0;i<toread;i++)
		if(!bd_readblock(startsector+i, (unsigned char *)buffer+i*BLOCK_SIZE)) {
			printf("E: Memory card failed (Cluster), sector %d\n", startsector+i);
			return 0;
		}
	return 1;
}

int fatfs_load(const char *filename, char *buffer, int size, int *realsize)
{
	const struct directory_entry *entry;
	int cluster_size;
	int cluster;
	int n;
	
	cluster_size = fatfs_sectors_per_cluster*BLOCK_SIZE;
	size /= BLOCK_SIZE;
	
	entry = fatfs_find_file_by_name(filename);
	if(entry == NULL) {
		printf("E: File not found: %s\n", filename);
		return 0;
	}
	
	if(realsize != NULL) *realsize = le32toh(entry->file_size);
	
	n = 0;
	cluster = le16toh(entry->first_cluster);
	while(size > 0) {
		if(!fatfs_load_cluster(cluster, buffer+n*cluster_size, size))
			return 0;
		size -= fatfs_sectors_per_cluster;
		n++;
		cluster = fatfs_read_fat(cluster);
		if(cluster >= 0xFFF8) break;
		if(cluster == -1) return 0;
	}
	//putsnonl("\n");
	
	return n*cluster_size;
}

void fatfs_done(void)
{
	bd_done();
}
