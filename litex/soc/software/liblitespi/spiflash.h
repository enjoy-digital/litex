#ifndef __LITESPI_FLASH_H
#define __LITESPI_FLASH_H

#include <generated/csr.h>

#define SPI_FLASH_BLOCK_SIZE	256
#define CRC32_ERASED_FLASH	0xFEA8A821

typedef enum {
	SPI_MODE_MMAP = 0,
	SPI_MODE_MASTER = 1,
} spi_mode;

int spiflash_freq_init(void);
void spiflash_dummy_bits_setup(unsigned int dummy_bits);
void spiflash_init(void);

#endif /* __LITESPI_FLASH_H */
