#ifndef __SPIFLASH_H
#define __SPIFLASH_H

void write_to_flash_page(unsigned int addr, unsigned char *c, unsigned int len);
void erase_flash_sector(unsigned int addr);

#endif /* __SPIFLASH_H */
