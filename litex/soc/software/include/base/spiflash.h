#ifndef __SPIFLASH_H
#define __SPIFLASH_H

#define FLASH_ENV_ADDRESS 16777216
#define ENV_VAR_SIZE 1024
#define JSMN_TOKEN_SIZE 10

void write_to_flash_page(unsigned int addr, const unsigned char *c, unsigned int len);
void erase_flash_sector(unsigned int addr);
void erase_flash_subsector(unsigned int addr);
void erase_flash(void);
void write_to_flash(unsigned int addr, const unsigned char *c, unsigned int len);

#endif /* __SPIFLASH_H */
