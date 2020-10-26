// This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD

#ifndef __SATA_H
#define __SATA_H

#include <generated/csr.h>

#ifdef CSR_SATA_BLOCK2MEM_BASE

/*-----------------------------------------------------------------------*/
/* SATA user functions                                                   */
/*-----------------------------------------------------------------------*/

int sata_init(void);
void sata_read(uint32_t sector, uint32_t count, uint8_t* buf);

#endif /* CSR_SATA_BASE */

#endif /* __SATA_H */
