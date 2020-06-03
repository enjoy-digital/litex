#ifndef __SPISDCARD_H
#define __SPISDCARD_H

#include <generated/csr.h>

#ifdef CSR_SPISDCARD_BASE

#define USE_SPISCARD_RECLOCKING

int spi_sdcard_init(uint32_t device);
int spi_sdcard_read_sector(uint32_t device, uint32_t lba,uint_least8_t *buf);

uint8_t spi_sdcard_goidle(void);

uint8_t readSector(uint32_t sectorNumber, uint8_t *storage);

#endif /* CSR_SPISDCARD_BASE */

#endif /* __SPISDCARD_H */
