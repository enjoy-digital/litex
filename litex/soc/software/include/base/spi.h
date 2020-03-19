int spi_sdcard_init(uint32_t device);
int spi_sdcard_read_sector(uint32_t device, unsigned long lba,unsigned char *buf);

unsigned char spi_sdcard_goidle(void);
unsigned char spi_sdcard_readMBR(void);
unsigned char spi_sdcard_readFile(char *, char *, unsigned long);
