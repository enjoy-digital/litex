// This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <generated/csr.h>
#include <generated/mem.h>
#include <system.h>

#include "fat/ff.h"
#include "fat/diskio.h"
#include "sata.h"

#ifdef CSR_SATA_BLOCK2MEM_BASE

/*-----------------------------------------------------------------------*/
/* SATA user functions                                                   */
/*-----------------------------------------------------------------------*/

int sata_init(void) {
	return 1; /* FIXME: TODO. */
}

void sata_read(uint32_t block, uint32_t count, uint8_t* buf)
{
	uint32_t i;
	for (i=0; i<count; i++) {
		sata_block2mem_base_write(((uint32_t) buf) + i*512);
		sata_block2mem_sector_write(block + i);
		sata_block2mem_start_write(1);
		while ((sata_block2mem_done_read() & 0x1) == 0);
	}

#ifndef CONFIG_CPU_HAS_DMA_BUS
	/* Flush CPU caches */
	flush_cpu_dcache();
#ifdef CONFIG_L2_SIZE
	flush_l2_cache();
#endif
#endif
}

/*-----------------------------------------------------------------------*/
/* SATA FatFs disk functions                                             */
/*-----------------------------------------------------------------------*/

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

DRESULT disk_read(uint8_t drv, uint8_t *buf, uint32_t block, uint32_t count) {
	sata_read(block, count, buf);
	return RES_OK;
}

#endif /* CSR_SATA_BLOCK2MEM_BASE */
