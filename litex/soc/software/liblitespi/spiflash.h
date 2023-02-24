#ifndef __LITESPI_FLASH_H
#define __LITESPI_FLASH_H

#ifdef __cplusplus
extern "C" {
#endif

#define SPI_FLASH_BLOCK_SIZE 256
#define CRC32_ERASED_FLASH	 0xFEA8A821

int spiflash_freq_init(void);
void spiflash_dummy_bits_setup(unsigned int dummy_bits);
void spiflash_memspeed(void);
void spiflash_init(void);

#ifdef __cplusplus
}
#endif

#endif /* __LITESPI_FLASH_H */
