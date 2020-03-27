int spi_sdcard_init(uint32_t device);
int spi_sdcard_read_sector(uint32_t device, uint32_t lba,uint_least8_t *buf);

uint8_t spi_sdcard_goidle(void);
uint8_t spi_sdcard_readMBR(void);
uint8_t spi_sdcard_readFile(char *, char *, unsigned long);
