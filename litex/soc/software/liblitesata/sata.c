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


	for (timeout=10; timeout>0; timeout--) {
		/* Check SATA PHY status */
		if (sata_phy_status_read() & 0x1)
			return 1;

		/* Reset SATA PHY */
		sata_phy_enable_write(0);
		sata_phy_enable_write(1);

		/* Wait for 10ms */
		busy_wait(10);
	}

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
			sata_sector2mem_base_write((uint64_t) buf);
			sata_sector2mem_sector_write(sector + i);
			sata_sector2mem_start_write(1);
			while ((sata_sector2mem_done_read() & 0x1) == 0);
			done = ((sata_sector2mem_error_read() & 0x1) == 0);
			busy_wait_us(10);
		}
		buf += 512;
	}

#ifndef CONFIG_CPU_HAS_DMA_BUS
	/* Flush CPU caches */
	flush_cpu_dcache();
#ifdef CONFIG_L2_SIZE
	flush_l2_cache();
#endif
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
			sata_mem2sector_base_write((uint64_t) buf);
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

DSTATUS disk_status(uint8_t drv) {
	if (drv) return STA_NOINIT;
	return satastatus;
}

DSTATUS disk_initialize(uint8_t drv) {
	if (drv) return STA_NOINIT;
	if (satastatus)
		satastatus = sata_init() ? 0 : STA_NOINIT;
	return satastatus;
}

DRESULT disk_read(uint8_t drv, uint8_t *buf, uint32_t sector, uint32_t count) {
	sata_read(sector, count, buf);
	return RES_OK;
}

#endif /* CSR_SATA_SECTOR2MEM_BASE */
