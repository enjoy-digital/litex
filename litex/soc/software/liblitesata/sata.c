// This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
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

int sata_init(void) {
	uint16_t timeout;
	uint8_t  buf[512];

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

		/* Initiate a SATA Read */
		sata_sector2mem_base_write((uint64_t)(uintptr_t) buf);
		sata_sector2mem_sector_write(0);
		sata_sector2mem_start_write(1);

		/* Wait for 10ms */
		busy_wait(10);

		/* Check SATA Read status */
		if ((sata_sector2mem_done_read() & 0x1) == 0)
			continue;

		/* Init succeeded */
		return 1;
	}

	/* Init failed */
	return 0;
}

#endif

#ifdef CSR_SATA_SECTOR2MEM_BASE

void sata_read(uint32_t sector, uint32_t count, uint8_t* buf)
{
	uint32_t i;

	/* Write sectors */
	for (i=0; i<count; i++) {
		uint8_t done = 0;
		while (done == 0) {
			sata_sector2mem_base_write((uint64_t)(uintptr_t) buf);
			sata_sector2mem_sector_write(sector + i);
			sata_sector2mem_start_write(1);
			while ((sata_sector2mem_done_read() & 0x1) == 0);
			done = ((sata_sector2mem_error_read() & 0x1) == 0);
			busy_wait_us(10);
		}
		buf += 512;
	}

#ifndef CONFIG_CPU_HAS_DMA_BUS
	/* Flush caches */
	flush_cpu_dcache();
	flush_l2_cache();
#endif
}

#endif

#ifdef CSR_SATA_MEM2SECTOR_BASE

void sata_write(uint32_t sector, uint32_t count, uint8_t* buf)
{
	uint32_t i;

	/* Write sectors */
	for (i=0; i<count; i++) {
		uint8_t done = 0;
		while (done == 0) {
			sata_mem2sector_base_write((uint64_t)(uintptr_t) buf);
			sata_mem2sector_sector_write(sector + i);
			sata_mem2sector_start_write(1);
			while ((sata_sector2mem_done_read() & 0x1) == 0);
			done = ((sata_sector2mem_error_read() & 0x1) == 0);
			busy_wait_us(10);
		}
		buf += 512;
	}
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
		satastatus = sata_init() ? 0 : STA_NOINIT;
	return satastatus;
}

static DRESULT sata_disk_read(BYTE drv, BYTE *buf, LBA_t sector, UINT count) {
	sata_read(sector, count, buf);
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
