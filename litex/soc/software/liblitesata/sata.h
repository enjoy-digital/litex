// This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD

#ifndef __SATA_H
#define __SATA_H

#ifdef __cplusplus
extern "C" {
#endif

#include <generated/csr.h>

/*-----------------------------------------------------------------------*/
/* SATA user functions                                                   */
/*-----------------------------------------------------------------------*/

#ifdef CSR_SATA_PHY_BASE

int sata_init(int show);
void fatfs_set_ops_sata(void);

#endif

#ifdef CSR_SATA_SECTOR2MEM_BASE

void sata_read(uint32_t sector, uint32_t count, uint8_t* buf);

#endif

#ifdef CSR_SATA_MEM2SECTOR_BASE

void sata_write(uint32_t sector, uint32_t count, uint8_t* buf);

#endif

#ifdef __cplusplus
}
#endif

#endif /* __SATA_H */
