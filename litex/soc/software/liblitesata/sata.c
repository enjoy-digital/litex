// This file is Copyright (c) 2020-2022 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <generated/csr.h>
#include <generated/mem.h>
#include <system.h>

#include <libfatfs/ff.h>
#include <libfatfs/diskio.h>
#include "sata.h"

/*-----------------------------------------------------------------------*/
/* SATA user functions                                                   */
/*-----------------------------------------------------------------------*/

#ifdef CSR_SATA_PHY_BASE

int sata_init(int show) {
	uint16_t timeout;
	int i;
	uint32_t data;
	uint16_t buf[128];
	uint8_t  model[38];
	uint64_t sectors;
	unsigned capacity;

	for (timeout=16; timeout>0; timeout--) {
		/* Reset SATA PHY */
		sata_phy_enable_write(0);
		busy_wait(1);
		sata_phy_enable_write(1);

		/* Wait for 100ms */
		busy_wait(100);

		/* Check SATA PHY status */
		if ((sata_phy_status_read() & 0x1) == 0)
			/* Re-initialize if failing */
			continue;

		/* Initiate a SATA Identify */
		sata_identify_start_write(1);

		/* Wait for 100ms */
		busy_wait(100);

		/* Check SATA Identify status */
		if ((sata_identify_done_read() & 0x1) == 0)
			/* Re-initialize if failing */
			continue;

		if (show)
			printf("\n");

		/* Dump Idenfify response to buf */
		i = 0;
		while (sata_identify_source_valid_read() && (i < 128)) {
			data = sata_identify_source_data_read();
			sata_identify_source_ready_write(1);
			buf[i+0] = ((data >>  0) & 0xffff);
			buf[i+1] = ((data >> 16) & 0xffff);
			i += 2;
		}

		/* Get Disk Model from buf */
		i = 0;
		memset(model, 0, 38);
		for (i=0; i<18; i++) {
			model[2*i + 0] = (buf[27+i] >> 8) & 0xff;
			model[2*i + 1] = (buf[27+i] >> 0) & 0xff;
		}
		if (show)
			printf("Model:    %s\n", model);

		/* Get Disk Capacity from buf */
		sectors = 0;
		sectors += (((uint64_t) buf[100]) <<  0);
		sectors += (((uint64_t) buf[101]) << 16);
		sectors += (((uint64_t) buf[102]) << 32);
		sectors += (((uint64_t) buf[103]) << 48);
		capacity = sectors/(1000*1000*500/256);
		if (show)
			printf("Capacity: %dGB\n", capacity);

		/* Init succeeded */
		return 1;
	}

	/* Init failed */
	return 0;
}

#endif

/* Bound retries and completion waits: a missing or failing disk must not hang
   the BIOS forever. */
#ifndef SATA_OP_RETRIES
#define SATA_OP_RETRIES 8
#endif
#ifndef SATA_OP_TIMEOUT_US
#define SATA_OP_TIMEOUT_US 100000
#endif

#ifdef CSR_SATA_SECTOR2MEM_BASE

int sata_read(uint32_t sector, uint32_t count, uint8_t* buf)
{
	unsigned int retries;
	unsigned int timeout;

	for (retries = 0; retries < SATA_OP_RETRIES; retries++) {
		sata_sector2mem_base_write((uint64_t)(uintptr_t) buf);
		sata_sector2mem_sector_write(sector);
		sata_sector2mem_nsectors_write(count);
		sata_sector2mem_start_write(1);
		for (timeout = SATA_OP_TIMEOUT_US; timeout > 0; timeout--) {
			if ((sata_sector2mem_done_read() & 0x1) != 0) {
				if ((sata_sector2mem_error_read() & 0x1) == 0) {
#ifndef CONFIG_CPU_HAS_DMA_BUS
					/* Flush caches */
					flush_cpu_dcache();
					flush_l2_cache();
#endif
					return 0;
				}
				/* Error: retry */
				break;
			}
			busy_wait_us(1);
		}
		busy_wait_us(10);
	}

	return -1;
}

#endif

#ifdef CSR_SATA_MEM2SECTOR_BASE

int sata_write(uint32_t sector, uint32_t count, uint8_t* buf)
{
	unsigned int retries;
	unsigned int timeout;

	/* Write sectors */
	for (retries = 0; retries < SATA_OP_RETRIES; retries++) {
		sata_mem2sector_base_write((uint64_t)(uintptr_t) buf);
		sata_mem2sector_sector_write(sector);
		sata_mem2sector_nsectors_write(count);
		sata_mem2sector_start_write(1);
		for (timeout = SATA_OP_TIMEOUT_US; timeout > 0; timeout--) {
			if ((sata_mem2sector_done_read() & 0x1) != 0) {
				if ((sata_mem2sector_error_read() & 0x1) == 0)
					return 0;
				/* Error: retry */
				break;
			}
			busy_wait_us(1);
		}
		busy_wait_us(10);
	}

	return -1;
}

#endif

/*-----------------------------------------------------------------------*/
/* SATA FatFs disk functions                                             */
/*-----------------------------------------------------------------------*/

#ifdef CSR_SATA_SECTOR2MEM_BASE

static DSTATUS satastatus = STA_NOINIT;

static DSTATUS sata_disk_status(BYTE drv) {
	if (drv) return STA_NOINIT;
	return satastatus;
}

static DSTATUS sata_disk_initialize(BYTE drv) {
	if (drv) return STA_NOINIT;
	if (satastatus)
		satastatus = sata_init(0) ? 0 : STA_NOINIT;
	return satastatus;
}

static DRESULT sata_disk_read(BYTE drv, BYTE *buf, LBA_t sector, UINT count) {
	if (sata_read(sector, count, buf) != 0)
		return RES_ERROR;
	return RES_OK;
}

static DISKOPS SataDiskOps = {
	.disk_initialize = sata_disk_initialize,
	.disk_status = sata_disk_status,
	.disk_read = sata_disk_read,
};

void fatfs_set_ops_sata(void) {
	FfDiskOps = &SataDiskOps;
}

#endif /* CSR_SATA_SECTOR2MEM_BASE */
