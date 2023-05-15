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
int spiflash_write_stream(uint32_t addr, uint8_t *stream, uint32_t len);
void spiflash_erase_range(uint32_t addr, uint32_t len);

#ifdef __cplusplus
}
#endif

#endif /* __LITESPI_FLASH_H */
